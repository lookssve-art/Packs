"""Parse drop rate data from various sources into DropRateSnapshot."""

from __future__ import annotations

import datetime
import re
from typing import Any

from src.models.dataclasses import DropRateSnapshot


def parse_drop_rates_from_api(
    data: dict[str, Any],
    pack_type: str,
) -> DropRateSnapshot | None:
    """Parse drop rates from a discovered API response.

    Handles multiple possible response structures.
    """
    rates: dict[str, float] = {}

    # Structure 1: {"rates": {"holographic": 0.02, ...}}
    if "rates" in data and isinstance(data["rates"], dict):
        for rarity, rate in data["rates"].items():
            rates[rarity.lower()] = float(rate)

    # Structure 2: {"tiers": [{"name": "Holographic", "rate": 0.02}, ...]}
    elif "tiers" in data and isinstance(data["tiers"], list):
        for tier in data["tiers"]:
            name = tier.get("name", "").lower()
            rate = tier.get("rate") or tier.get("probability") or tier.get("chance")
            if name and rate is not None:
                rates[name] = float(rate)

    # Structure 3: {"dropRates": {"Holographic": "2%", ...}}
    elif "dropRates" in data:
        for rarity, rate_str in data["dropRates"].items():
            rates[rarity.lower()] = _parse_percentage(str(rate_str))

    if not rates:
        return None

    # Normalize rates to sum to 1.0 if they don't already
    total = sum(rates.values())
    if total > 0 and abs(total - 1.0) > 0.01:
        rates = {k: v / total for k, v in rates.items()}

    return DropRateSnapshot(
        timestamp=datetime.datetime.utcnow(),
        pack_type=pack_type,
        rates=rates,
        source="api",
    )


def parse_drop_rates_from_scrape(
    scraped_data: dict[str, Any],
    pack_type: str,
) -> DropRateSnapshot | None:
    """Parse drop rates from Playwright-scraped page data.

    Expected structure from scraper:
    {"tiers": [{"name": "Holographic", "percentage": "2.00%", "value_range": "$500-$2000"}, ...]}
    """
    tiers = scraped_data.get("tiers", [])
    if not tiers:
        return None

    rates: dict[str, float] = {}
    for tier in tiers:
        name = (tier.get("name") or "").lower().strip()
        pct = tier.get("percentage") or tier.get("rate") or tier.get("chance")
        if name and pct is not None:
            rates[name] = _parse_percentage(str(pct))

    if not rates:
        return None

    # Normalize
    total = sum(rates.values())
    if total > 0 and abs(total - 1.0) > 0.01:
        rates = {k: v / total for k, v in rates.items()}

    return DropRateSnapshot(
        timestamp=datetime.datetime.utcnow(),
        pack_type=pack_type,
        rates=rates,
        source="scraper",
    )


def parse_drop_rates_manual(
    rates: dict[str, float],
    pack_type: str,
) -> DropRateSnapshot:
    """Create a snapshot from manually entered rates."""
    return DropRateSnapshot(
        timestamp=datetime.datetime.utcnow(),
        pack_type=pack_type,
        rates=rates,
        source="manual",
    )


def _parse_percentage(s: str) -> float:
    """Parse a percentage string like '2.00%' or '0.02' to a float in [0, 1]."""
    s = s.strip()
    if s.endswith("%"):
        return float(s.rstrip("%")) / 100.0
    val = float(s)
    # If value > 1, assume it's a percentage
    if val > 1.0:
        return val / 100.0
    return val
