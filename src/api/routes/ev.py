"""GET /api/ev/all and /api/ev/{pack_type}/history — EV computations."""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import (
    get_ev_repo,
    get_pack_type_repo,
    get_pull_repo,
    get_settings,
    get_snapshot_repo,
)
from src.models.dataclasses import PackTypeInfo
from src.models.ev_calculator import compute_all_evs

router = APIRouter(tags=["ev"])


@router.get("/ev/all")
def get_all_ev(
    half_life: float = Query(default=24.0, ge=1, le=168),
    time_window: int = Query(default=0, ge=0, description="Hours (0=all)"),
    settings=Depends(get_settings),
    pull_repo=Depends(get_pull_repo),
    pack_type_repo=Depends(get_pack_type_repo),
    snapshot_repo=Depends(get_snapshot_repo),
):
    pack_types = pack_type_repo.get_all_active()
    if not pack_types:
        from config.constants import KNOWN_PACKS
        pack_types = [
            PackTypeInfo(slug=s, display_name=s.title(), cost_usd=i["cost"],
                         sellback_rate=i.get("sellback_rate"))
            for s, i in KNOWN_PACKS.items()
        ]

    since = None
    if time_window > 0:
        since = datetime.datetime.utcnow() - datetime.timedelta(hours=time_window)

    pulls = pull_repo.get_recent(limit=settings.max_pulls_window, since=since)

    published_rates: dict[str, dict[str, float]] = {}
    for pack in pack_types:
        snap = snapshot_repo.get_latest(pack.slug)
        if snap:
            published_rates[pack.slug] = snap.rates

    ev_results = compute_all_evs(
        all_pulls=pulls,
        pack_types=pack_types,
        published_rates=published_rates or None,
        half_life_hours=half_life,
        prior_strength=settings.prior_strength,
    )

    return [
        {
            "pack_type": ev.pack_type,
            "ev": round(ev.ev, 2),
            "ev_ratio": round(ev.ev_ratio, 4),
            "pack_cost": ev.pack_cost,
            "confidence_tier": ev.confidence_tier,
            "obs_count": ev.obs_count,
            "p_rare_plus": round(ev.p_rare_plus, 4),
            "p_super_rare": round(ev.p_super_rare, 4),
            "conservative_score": round(ev.conservative_score, 4),
            "model_mode": ev.model_mode,
            "rarity_posteriors": {
                k: [round(v[0], 6), round(v[1], 6), round(v[2], 6)]
                for k, v in ev.rarity_posteriors.items()
            },
            "calibrated_values": {
                k: round(v, 2) for k, v in ev.calibrated_values.items()
            },
        }
        for ev in ev_results
    ]


@router.get("/ev/{pack_type}/history")
def get_ev_history(
    pack_type: str,
    limit: int = Query(default=200, le=1000),
    ev_repo=Depends(get_ev_repo),
):
    history = ev_repo.get_history(pack_type, limit)
    return [
        {
            "timestamp": h["timestamp"],
            "ev_value": h["ev_value"],
            "ev_ratio": h["ev_ratio"],
            "pack_cost": h["pack_cost"],
            "confidence_tier": h["confidence_tier"],
            "obs_count": h["obs_count"],
        }
        for h in history
    ]
