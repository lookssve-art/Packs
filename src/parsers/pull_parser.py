"""Parse raw API/scraper data into Pull dataclass objects."""

from __future__ import annotations

import datetime
import hashlib
from typing import Any

from config.constants import (
    DEFAULT_SOL_USD,
    PACK_TYPE_VALUE_THRESHOLDS_USD,
    RARITY_VALUE_THRESHOLDS_USD,
)
from src.models.dataclasses import Pull

# Module-level SOL price, updated by orchestrator
_sol_usd_price: float = DEFAULT_SOL_USD


def set_sol_price(price: float) -> None:
    """Update the SOL/USD price used for conversions."""
    global _sol_usd_price
    if price > 0:
        _sol_usd_price = price


def get_sol_price() -> float:
    """Get current SOL/USD price."""
    return _sol_usd_price


def _sol_to_usd(sol_amount: float) -> float:
    """Convert SOL amount to USD."""
    return sol_amount * _sol_usd_price


def _infer_pack_type_from_usd(value_usd: float) -> str:
    """Infer which pack a card likely came from based on its USD value."""
    if value_usd >= PACK_TYPE_VALUE_THRESHOLDS_USD["emerald"]:
        return "emerald"
    elif value_usd >= PACK_TYPE_VALUE_THRESHOLDS_USD["sapphire"]:
        return "sapphire"
    return "ruby"


def _infer_rarity_from_usd(value_usd: float) -> str:
    """Infer card rarity from its USD value."""
    if value_usd >= RARITY_VALUE_THRESHOLDS_USD["epic"]:
        return "epic"
    elif value_usd >= RARITY_VALUE_THRESHOLDS_USD["rare"]:
        return "rare"
    elif value_usd >= RARITY_VALUE_THRESHOLDS_USD["uncommon"]:
        return "uncommon"
    return "common"


def _normalize_rarity(raw: str) -> str:
    """Normalize rarity strings from various sources to our canonical names."""
    r = raw.strip().lower()
    mapping = {
        "holographic": "epic",
        "holo": "epic",
        "gold": "rare",
        "silver": "uncommon",
        "gloss": "common",
        "epic": "epic",
        "rare": "rare",
        "uncommon": "uncommon",
        "common": "common",
    }
    return mapping.get(r, "common")


def parse_me_activity(activity: dict[str, Any], pack_type: str = "") -> Pull | None:
    """Parse a Magic Eden v2 collection activity into a Pull.

    Expected fields from ME API /v2/collections/{symbol}/activities:
    - signature (transaction signature)
    - type (e.g. 'buyNow', 'list', etc.)
    - tokenMint
    - blockTime
    - buyer / seller
    - price (in SOL)
    - image
    - collectionSymbol
    """
    sig = activity.get("signature", "")
    mint = activity.get("tokenMint", "")
    if not sig or not mint:
        return None

    pull_id = f"me_activity:{sig}:{mint}"

    block_time = activity.get("blockTime")
    if block_time:
        ts = datetime.datetime.utcfromtimestamp(block_time)
    else:
        ts = datetime.datetime.utcnow()

    # Price from ME API is in SOL — convert to USD
    price_sol = activity.get("price")
    if price_sol is not None:
        value_usd = _sol_to_usd(float(price_sol))
    else:
        value_usd = None

    # Use enriched rarity from token metadata if available, else infer from USD value
    enriched_rarity = activity.get("_enriched_rarity")
    if enriched_rarity:
        rarity = _normalize_rarity(enriched_rarity)
    elif value_usd is not None:
        rarity = _infer_rarity_from_usd(value_usd)
    else:
        rarity = "common"

    # Infer pack type from value if the source is a generic collection symbol
    inferred_pack = pack_type
    if pack_type in ("collector_crypt", "") and value_usd is not None:
        inferred_pack = _infer_pack_type_from_usd(value_usd)
    elif not pack_type:
        inferred_pack = "sapphire"

    return Pull(
        pull_id=pull_id,
        timestamp=ts,
        pack_type=inferred_pack,
        rarity=rarity,
        card_name=activity.get("name"),
        token_mint=mint,
        estimated_value=round(value_usd, 2) if value_usd is not None else None,
        image_url=activity.get("image"),
        source="api_collection",
    )


def parse_packs_api_pull(data: dict[str, Any]) -> Pull | None:
    """Parse a pull from a discovered Packs-specific API endpoint."""
    pull_id = data.get("id") or data.get("pull_id") or data.get("transactionId")
    if not pull_id:
        content = f"{data.get('timestamp', '')}{data.get('cardName', '')}{data.get('value', '')}"
        pull_id = f"packs:{hashlib.sha256(content.encode()).hexdigest()[:16]}"

    ts_raw = data.get("timestamp") or data.get("createdAt") or data.get("date")
    if isinstance(ts_raw, (int, float)):
        ts = datetime.datetime.utcfromtimestamp(ts_raw)
    elif isinstance(ts_raw, str):
        try:
            ts = datetime.datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            ts = datetime.datetime.utcnow()
    else:
        ts = datetime.datetime.utcnow()

    # Extract rarity and normalize
    raw_rarity = (
        data.get("rarity", "")
        or data.get("tier", "")
        or data.get("rarityTier", "")
        or "unknown"
    )
    rarity = _normalize_rarity(raw_rarity)

    # Extract value (already in USD from packs API)
    value = data.get("value") or data.get("estimatedValue") or data.get("marketValue")
    estimated_value = float(value) if value else None

    payout = data.get("payout") or data.get("payoutValue") or data.get("sellbackValue")
    payout_value = float(payout) if payout else None

    return Pull(
        pull_id=str(pull_id),
        timestamp=ts,
        pack_type=data.get("packType", data.get("pack_type", "unknown")).lower(),
        rarity=rarity,
        card_name=data.get("cardName") or data.get("card_name") or data.get("name"),
        card_id=data.get("cardId") or data.get("card_id"),
        token_mint=data.get("tokenMint") or data.get("mint"),
        value_bucket=data.get("valueBucket") or data.get("value_bucket"),
        estimated_value=estimated_value,
        payout_value=payout_value,
        image_url=data.get("imageUrl") or data.get("image_url") or data.get("image"),
        source="api_packs",
    )


def parse_scraped_pull(data: dict[str, Any]) -> Pull | None:
    """Parse a pull extracted by the Playwright scraper."""
    pull_id = data.get("pull_id")
    if not pull_id:
        content = f"{data.get('card_name', '')}{data.get('value', '')}{data.get('timestamp', '')}"
        pull_id = f"scrape:{hashlib.sha256(content.encode()).hexdigest()[:16]}"

    ts_raw = data.get("timestamp")
    if isinstance(ts_raw, str):
        try:
            ts = datetime.datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            ts = datetime.datetime.utcnow()
    elif isinstance(ts_raw, (int, float)):
        ts = datetime.datetime.utcfromtimestamp(ts_raw)
    else:
        ts = datetime.datetime.utcnow()

    raw_rarity = (data.get("rarity") or "unknown")
    rarity = _normalize_rarity(raw_rarity)

    value = data.get("value") or data.get("estimated_value")
    estimated_value = float(value) if value else None

    return Pull(
        pull_id=str(pull_id),
        timestamp=ts,
        pack_type=(data.get("pack_type") or "unknown").lower(),
        rarity=rarity,
        card_name=data.get("card_name"),
        card_id=data.get("card_id"),
        value_bucket=data.get("value_bucket"),
        estimated_value=estimated_value,
        payout_value=float(data["payout_value"]) if data.get("payout_value") else None,
        image_url=data.get("image_url"),
        source="scraper",
    )
