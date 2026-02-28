"""Static constants and fallback values."""

from __future__ import annotations

# Rarity tiers in order from rarest to most common
RARITY_ORDER = ["holographic", "gold", "silver", "gloss"]

# Known pack defaults (used when dynamic discovery hasn't run yet)
KNOWN_PACKS = {
    "ruby": {"cost": 25.0, "sellback_rate": 0.80},
    "sapphire": {"cost": 50.0, "sellback_rate": 0.85},
    "emerald": {"cost": 250.0, "sellback_rate": 0.90},
}

# Fallback value estimates per rarity per pack type
# Used ONLY when fewer than 3 observations exist (conservative)
FALLBACK_VALUES: dict[str, dict[str, float]] = {
    "ruby": {
        "holographic": 400.0,
        "gold": 80.0,
        "silver": 30.0,
        "gloss": 15.0,
    },
    "sapphire": {
        "holographic": 800.0,
        "gold": 150.0,
        "silver": 55.0,
        "gloss": 35.0,
    },
    "emerald": {
        "holographic": 4000.0,
        "gold": 600.0,
        "silver": 220.0,
        "gloss": 160.0,
    },
}

# Generic fallback for unknown pack types
GENERIC_FALLBACK_VALUES: dict[str, float] = {
    "holographic": 1000.0,
    "gold": 200.0,
    "silver": 80.0,
    "gloss": 40.0,
}

# Uninformative Dirichlet prior (equal weight to all rarities)
UNINFORMATIVE_PRIOR = [1.0, 1.0, 1.0, 1.0]

# Confidence tier labels
CONFIDENCE_VERY_CONSERVATIVE = "very_conservative"
CONFIDENCE_PARTIAL = "partial"
CONFIDENCE_CALIBRATED = "calibrated"
