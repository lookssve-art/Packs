"""FastAPI application — serves REST API, WebSocket, and static frontend.

Startup: initializes DB, starts collector as background task, sets up WebSocket manager.
Shutdown: cancels collector, closes connections.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config.settings import Settings
from src.api.routes import alerts, ev, packs, pulls, rankings, snapshots, status, ws
from src.api.websocket_manager import WebSocketManager
from src.collector.orchestrator import Orchestrator
from src.models.ev_calculator import compute_all_evs
from src.storage.database import get_connection, init_db
from src.storage.repositories import (
    AlertRepository,
    PackTypeRepository,
    PullRepository,
    SnapshotRepository,
)

logger = logging.getLogger(__name__)

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")


async def _collector_loop(
    orch: Orchestrator,
    settings: Settings,
    ws_manager: WebSocketManager,
) -> None:
    """Background task: run collector cycles and broadcast results via WebSocket."""
    while True:
        try:
            summary = await orch.run_cycle()

            # Update status route state
            status.get_status._cycle_count = orch.cycle_count  # type: ignore[attr-defined]
            status.get_status._last_cycle = summary.get("timestamp")  # type: ignore[attr-defined]

            # Broadcast to WebSocket clients
            if ws_manager.active:
                new_pulls_data = []
                ev_data = []
                alerts_data = []

                if summary.get("new_pulls", 0) > 0:
                    conn = orch.conn
                    repo = PullRepository(conn)
                    recent = repo.get_recent(limit=summary["new_pulls"])
                    new_pulls_data = [
                        {
                            "pull_id": p.pull_id,
                            "timestamp": p.timestamp.isoformat(),
                            "pack_type": p.pack_type,
                            "rarity": p.rarity,
                            "card_name": p.card_name,
                            "estimated_value": p.estimated_value,
                            "payout_value": p.payout_value,
                            "image_url": p.image_url,
                        }
                        for p in recent
                    ]

                # Compute fresh EV for broadcast
                conn = orch.conn
                pack_repo = PackTypeRepository(conn)
                pull_repo = PullRepository(conn)
                snap_repo = SnapshotRepository(conn)
                alert_repo = AlertRepository(conn)

                pack_types = pack_repo.get_all_active()
                if pack_types:
                    all_pulls = pull_repo.get_recent(limit=settings.max_pulls_window)
                    pub_rates: dict = {}
                    for pt in pack_types:
                        s = snap_repo.get_latest(pt.slug)
                        if s:
                            pub_rates[pt.slug] = s.rates

                    evs = compute_all_evs(
                        all_pulls=all_pulls,
                        pack_types=pack_types,
                        published_rates=pub_rates or None,
                        half_life_hours=settings.default_half_life_hours,
                    )
                    ev_data = [
                        {
                            "pack_type": e.pack_type,
                            "ev": round(e.ev, 2),
                            "ev_ratio": round(e.ev_ratio, 4),
                            "p_rare_plus": round(e.p_rare_plus, 4),
                            "p_super_rare": round(e.p_super_rare, 4),
                            "confidence_tier": e.confidence_tier,
                            "obs_count": e.obs_count,
                            "conservative_score": round(e.conservative_score, 4),
                            "pack_cost": e.pack_cost,
                            "model_mode": e.model_mode,
                            "rarity_posteriors": {
                                k: [round(v[0], 6), round(v[1], 6), round(v[2], 6)]
                                for k, v in e.rarity_posteriors.items()
                            },
                            "calibrated_values": {
                                k: round(v, 2) for k, v in e.calibrated_values.items()
                            },
                        }
                        for e in evs
                    ]

                if summary.get("alerts_triggered", 0) > 0:
                    active = alert_repo.get_active(limit=5)
                    alerts_data = [
                        {
                            "id": a.id,
                            "alert_type": a.alert_type,
                            "pack_type": a.pack_type,
                            "severity": a.severity,
                            "message": a.message,
                            "timestamp": a.timestamp.isoformat(),
                        }
                        for a in active
                    ]

                await ws_manager.broadcast_cycle(
                    summary=summary,
                    ev_data=ev_data,
                    new_pulls=new_pulls_data,
                    alerts=alerts_data,
                )

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Collector cycle error: %s", e, exc_info=True)

        await asyncio.sleep(settings.poll_interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    settings = Settings()
    conn = get_connection(settings.db_path, check_same_thread=False)
    init_db(conn)

    ws_manager = WebSocketManager()

    app.state.settings = settings
    app.state.conn = conn
    app.state.ws_manager = ws_manager

    # Initialize and start collector
    orch = Orchestrator(settings)
    await orch.initialize()
    app.state.orchestrator = orch

    collector_task = asyncio.create_task(
        _collector_loop(orch, settings, ws_manager)
    )
    app.state.collector_task = collector_task

    logger.info(
        "App started. Collector polling every %ds. Web: http://%s:%d",
        settings.poll_interval_seconds,
        settings.web_host,
        settings.web_port,
    )

    yield

    # Shutdown
    collector_task.cancel()
    try:
        await collector_task
    except asyncio.CancelledError:
        pass
    await orch.shutdown()
    conn.close()
    logger.info("App shut down.")


app = FastAPI(
    title="Packs EV Tracker",
    description="Real-time Magic Eden Pokemon Pack analysis",
    lifespan=lifespan,
)

# CORS — allow Workers domain and localhost for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://key-of-silent-insight.solana-nft-portfolio-smorty-2026.workers.dev",
        "https://thekeyofsilentinsight.com",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(status.router, prefix="/api")
app.include_router(packs.router, prefix="/api")
app.include_router(ev.router, prefix="/api")
app.include_router(pulls.router, prefix="/api")
app.include_router(rankings.router, prefix="/api")
app.include_router(snapshots.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(ws.router)

# Static files
if os.path.isdir(WEB_DIR):
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/")
async def index():
    index_path = os.path.join(WEB_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Packs EV Tracker API", "docs": "/docs"}
