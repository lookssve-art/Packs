"""Parse raw API/scraper data into Pull dataclass objects."""

from __future__ import annotations

import datetime
import hashlib
from typing import Any

from src.models.dataclasses import Pull


def parse_me_activity(activity: dict[str, Any], pack_type: str = "") -> Pull | None:
    """Parse a Magic Eden v2 collection activity into a Pull.

    Expected fields from ME API /v2/collections/{symbol}/activities:
    - signature (transaction signature)
    - type (e.g. 'buyNow', 'list', etc.)
    - tokenMint
    - blockTime
    - buyer / seller
    - price
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

    price = activity.get("price")
    estimated_value = float(price) if price else None

    # Try to extract rarity from attributes or name
    rarity = _infer_rarity_from_activity(activity)

    return Pull(
        pull_id=pull_id,
        timestamp=ts,
        pack_type=pack_type or activity.get("collectionSymbol", "unknown"),
        rarity=rarity,
        card_name=activity.get("name"),
        token_mint=mint,
        estimated_value=estimated_value,
        image_url=activity.get("image"),
        source="api_collection",
    )


def parse_packs_api_pull(data: dict[str, Any]) -> Pull | None:
    """Parse a pull from a discovered Packs-specific API endpoint.

    Schema will be determined after endpoint discovery. This parser
    handles the most common expected structures.
    """
    # Generate pull_id from available identifiers
    pull_id = data.get("id") or data.get("pull_id") or data.get("transactionId")
    if not pull_id:
        # Create deterministic ID from content
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

    # Extract rarity — try multiple field names
    rarity = (
        data.get("rarity", "")
        or data.get("tier", "")
        or data.get("rarityTier", "")
        or "unknown"
    ).lower()

    # Extract value
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

    rarity = (data.get("rarity") or "unknown").lower()

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


def _infer_rarity_from_activity(activity: dict[str, Any]) -> str:
    """Try to infer rarity from activity data.

    Looks at attributes, name patterns, and price ranges.
    """
    # Check for explicit rarity field
    attrs = activity.get("attributes") or []
    for attr in attrs:
        if isinstance(attr, dict):
            trait = (attr.get("trait_type") or "").lower()
            if trait in ("rarity", "tier"):
                return str(attr.get("value", "unknown")).lower()

    # Check name for rarity keywords
    name = (activity.get("name") or "").lower()
    if "holographic" in name or "holo" in name:
        return "holographic"
    if "gold" in name:
        return "gold"
    if "silver" in name:
        return "silver"
    if "gloss" in name:
        return "gloss"

    # Infer from price if available
    price = activity.get("price")
    if price is not None:
        price_val = float(price)
        if price_val >= 500:
            return "holographic"
        elif price_val >= 100:
            return "gold"
        elif price_val >= 40:
            return "silver"
        else:
            return "gloss"

    return "unknown"
