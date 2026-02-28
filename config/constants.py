"""Static constants and fallback values."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Rarity tiers in order from rarest to most common
# Matches Collector Crypt / Magic Eden Packs rarity naming
# ---------------------------------------------------------------------------
RARITY_ORDER = ["epic", "rare", "uncommon", "common"]

# Display labels including official drop-rate percentages
RARITY_LABELS: dict[str, str] = {
    "epic": "Epic (1%)",
    "rare": "Rare (4%)",
    "uncommon": "Uncommon (15%)",
    "common": "Common (80%)",
}

# Drop-rate percentage per rarity for display
RARITY_PCT: dict[str, float] = {
    "epic": 1.0,
    "rare": 4.0,
    "uncommon": 15.0,
    "common": 80.0,
}

# ---------------------------------------------------------------------------
# Published drop rates from Collector Crypt Gacha Machine
# Source: gacha.collectorcrypt.com (verified Feb 2026)
# ---------------------------------------------------------------------------
PUBLISHED_DROP_RATES: dict[str, dict[str, float]] = {
    "sapphire": {
        "epic": 0.01,
        "rare": 0.04,
        "uncommon": 0.15,
        "common": 0.80,
    },
    "ruby": {
        "epic": 0.005,
        "rare": 0.035,
        "uncommon": 0.12,
        "common": 0.84,
    },
    "emerald": {
        "epic": 0.03,
        "rare": 0.07,
        "uncommon": 0.20,
        "common": 0.70,
    },
}

# ---------------------------------------------------------------------------
# Known pack defaults
# ---------------------------------------------------------------------------
KNOWN_PACKS = {
    "ruby": {"cost": 25.0, "sellback_rate": 0.80},
    "sapphire": {"cost": 50.0, "sellback_rate": 0.85},
    "emerald": {"cost": 250.0, "sellback_rate": 0.90},
}

# ---------------------------------------------------------------------------
# Published value ranges per rarity per pack type (USD)
# Source: Collector Crypt published card value ranges
# ---------------------------------------------------------------------------
FALLBACK_VALUES: dict[str, dict[str, float]] = {
    "ruby": {
        "epic": 120.0,
        "rare": 55.0,
        "uncommon": 28.0,
        "common": 16.0,
    },
    "sapphire": {
        "epic": 500.0,
        "rare": 160.0,
        "uncommon": 80.0,
        "common": 42.0,
    },
    "emerald": {
        "epic": 5000.0,
        "rare": 800.0,
        "uncommon": 320.0,
        "common": 190.0,
    },
}

# Map ME collection symbols to pack types they feed data into.
COLLECTION_PACK_MAP: dict[str, list[str]] = {
    "collector_crypt": ["ruby", "sapphire", "emerald"],
}

# Generic fallback for unknown pack types
GENERIC_FALLBACK_VALUES: dict[str, float] = {
    "epic": 500.0,
    "rare": 150.0,
    "uncommon": 80.0,
    "common": 40.0,
}

# ---------------------------------------------------------------------------
# SOL price (default, updated at runtime via CoinGecko)
# ---------------------------------------------------------------------------
DEFAULT_SOL_USD = 140.0

# USD value thresholds for rarity inference (after SOL->USD conversion)
RARITY_VALUE_THRESHOLDS_USD = {
    "epic": 250.0,
    "rare": 110.0,
    "uncommon": 60.0,
}

# Pack type inference from card USD value
PACK_TYPE_VALUE_THRESHOLDS_USD = {
    "emerald": 150.0,
    "sapphire": 30.0,
}

# Uninformative Dirichlet prior (equal weight to all rarities)
UNINFORMATIVE_PRIOR = [1.0, 1.0, 1.0, 1.0]

# Confidence tier labels
CONFIDENCE_VERY_CONSERVATIVE = "very_conservative"
CONFIDENCE_PARTIAL = "partial"
CONFIDENCE_CALIBRATED = "calibrated"
