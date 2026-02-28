"""GET /api/packs — available pack types."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from config.constants import PUBLISHED_DROP_RATES, RARITY_LABELS
from src.api.dependencies import get_pack_type_repo, get_settings

router = APIRouter(tags=["packs"])


@router.get("/packs")
def get_packs(
    settings=Depends(get_settings),
    pack_type_repo=Depends(get_pack_type_repo),
):
    packs = pack_type_repo.get_all_active()
    return [
        {
            "slug": p.slug,
            "display_name": p.display_name,
            "cost_usd": p.cost_usd,
            "sellback_rate": p.sellback_rate,
            "rarity_tiers": p.rarity_tiers,
            "is_active": p.is_active,
            "buy_url": settings.me_packs_url,
            "drop_rates": PUBLISHED_DROP_RATES.get(p.slug, {}),
            "rarity_labels": RARITY_LABELS,
        }
        for p in packs
    ]
