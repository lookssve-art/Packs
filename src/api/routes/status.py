"""GET /api/status — collector health and stats."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends

from src.api.dependencies import get_pack_type_repo, get_pull_repo, get_settings

router = APIRouter(tags=["status"])

_start_time = time.time()


@router.get("/status")
def get_status(
    settings=Depends(get_settings),
    pull_repo=Depends(get_pull_repo),
    pack_type_repo=Depends(get_pack_type_repo),
):
    counts = pull_repo.get_count_by_pack()
    packs = pack_type_repo.get_all_active()
    return {
        "collector_running": True,
        "cycle_count": getattr(get_status, "_cycle_count", 0),
        "last_cycle": getattr(get_status, "_last_cycle", None),
        "total_pulls": sum(counts.values()),
        "pull_counts": counts,
        "uptime_seconds": round(time.time() - _start_time, 1),
        "poll_interval": settings.poll_interval_seconds,
        "pack_types": [p.slug for p in packs],
    }
