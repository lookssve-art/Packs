"""GET /api/pulls/recent — recent pack rip results."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_pull_repo

router = APIRouter(tags=["pulls"])


@router.get("/pulls/recent")
def get_recent_pulls(
    pack_type: Optional[str] = None,
    limit: int = Query(default=50, le=500),
    pull_repo=Depends(get_pull_repo),
):
    pulls = pull_repo.get_recent(pack_type=pack_type, limit=limit)
    return [
        {
            "pull_id": p.pull_id,
            "timestamp": p.timestamp.isoformat(),
            "pack_type": p.pack_type,
            "rarity": p.rarity,
            "card_name": p.card_name,
            "estimated_value": p.estimated_value,
            "payout_value": p.payout_value,
            "image_url": p.image_url,
            "source": p.source,
        }
        for p in pulls
    ]
