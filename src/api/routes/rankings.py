"""GET /api/rankings — pack rankings across 4 modes."""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import (
    get_pack_type_repo,
    get_pull_repo,
    get_settings,
    get_snapshot_repo,
)
from src.models.dataclasses import PackTypeInfo
from src.models.ev_calculator import compute_all_evs
from src.recommender.ranker import get_all_rankings

router = APIRouter(tags=["rankings"])


@router.get("/rankings")
def get_rankings(
    half_life: float = Query(default=24.0, ge=1, le=168),
    time_window: int = Query(default=0, ge=0),
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

    from config.constants import PUBLISHED_DROP_RATES
    published_rates: dict[str, dict[str, float]] = dict(PUBLISHED_DROP_RATES)
    for pack in pack_types:
        snap = snapshot_repo.get_latest(pack.slug)
        if snap:
            published_rates[pack.slug] = snap.rates

    ev_results = compute_all_evs(
        all_pulls=pulls,
        pack_types=pack_types,
        published_rates=published_rates,
        half_life_hours=half_life,
        prior_strength=settings.prior_strength,
    )

    rankings = get_all_rankings(ev_results)

    return {
        mode: [
            {
                "rank": rp.rank,
                "pack_type": rp.pack_type,
                "score": round(rp.score, 6),
                "label": rp.label,
                "confidence_tier": rp.confidence_tier,
            }
            for rp in ranked
        ]
        for mode, ranked in rankings.items()
    }
