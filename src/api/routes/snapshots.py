"""GET /api/snapshots/{pack_type} — drop rate snapshot history."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_snapshot_repo

router = APIRouter(tags=["snapshots"])


@router.get("/snapshots/{pack_type}")
def get_snapshots(
    pack_type: str,
    limit: int = Query(default=50, le=500),
    snapshot_repo=Depends(get_snapshot_repo),
):
    history = snapshot_repo.get_history(pack_type, limit)
    return [
        {
            "id": s.id,
            "timestamp": s.timestamp.isoformat(),
            "pack_type": s.pack_type,
            "rates": s.rates,
            "source": s.source,
        }
        for s in history
    ]
