"""Value calibration model — estimates true average card value per rarity.

CRITICAL: Does NOT use bucket midpoints as default.
Uses observed pull values with recency weighting.
"""

from __future__ import annotations

import math
from collections import defaultdict

from config.constants import (
    CONFIDENCE_CALIBRATED,
    CONFIDENCE_PARTIAL,
    CONFIDENCE_VERY_CONSERVATIVE,
    FALLBACK_VALUES,
    GENERIC_FALLBACK_VALUES,
)
from src.models.confidence import get_confidence_tier


def calibrate_values(
    value_weight_pairs: dict[str, list[tuple[float, float]]],
    pack_type: str,
    fallback_multiplier: float = 0.8,
) -> dict[str, float]:
    """Compute calibrated average value per rarity from weighted observations.

    Args:
        value_weight_pairs: rarity -> list of (value, weight) from
            recency.weighted_values_by_rarity()
        pack_type: pack slug for looking up fallback values
        fallback_multiplier: conservative haircut on fallback values

    Returns:
        dict of rarity -> calibrated average value
    """
    pack_fallbacks = FALLBACK_VALUES.get(pack_type, GENERIC_FALLBACK_VALUES)

    result: dict[str, float] = {}
    for rarity, pairs in value_weight_pairs.items():
        if len(pairs) >= 3:
            # Enough data — weighted mean
            total_w = sum(w for _, w in pairs)
            if total_w > 0:
                result[rarity] = sum(v * w for v, w in pairs) / total_w
            else:
                result[rarity] = _get_fallback(rarity, pack_fallbacks, fallback_multiplier)
        else:
            # Insufficient data — use conservative fallback
            result[rarity] = _get_fallback(rarity, pack_fallbacks, fallback_multiplier)

    return result


def calibrate_values_with_confidence(
    value_weight_pairs: dict[str, list[tuple[float, float]]],
    pack_type: str,
    fallback_multiplier: float = 0.8,
    threshold_partial: int = 3,
    threshold_calibrated: int = 10,
) -> tuple[dict[str, float], dict[str, str], dict[str, int]]:
    """Calibrate values and return per-rarity confidence tiers.

    Returns:
        (calibrated_values, confidence_tiers, obs_counts)
    """
    pack_fallbacks = FALLBACK_VALUES.get(pack_type, GENERIC_FALLBACK_VALUES)

    values: dict[str, float] = {}
    tiers: dict[str, str] = {}
    counts: dict[str, int] = {}

    for rarity, pairs in value_weight_pairs.items():
        n = len(pairs)
        counts[rarity] = n
        tiers[rarity] = get_confidence_tier(n, threshold_partial, threshold_calibrated)

        if n >= threshold_partial:
            total_w = sum(w for _, w in pairs)
            if total_w > 0:
                values[rarity] = sum(v * w for v, w in pairs) / total_w
            else:
                values[rarity] = _get_fallback(rarity, pack_fallbacks, fallback_multiplier)
        else:
            values[rarity] = _get_fallback(rarity, pack_fallbacks, fallback_multiplier)

    return values, tiers, counts


def weighted_std(
    pairs: list[tuple[float, float]],
) -> float:
    """Compute weighted standard deviation."""
    if len(pairs) < 2:
        return 0.0
    total_w = sum(w for _, w in pairs)
    if total_w <= 0:
        return 0.0
    mean = sum(v * w for v, w in pairs) / total_w
    variance = sum(w * (v - mean) ** 2 for v, w in pairs) / total_w
    return math.sqrt(max(0.0, variance))


def _get_fallback(
    rarity: str,
    pack_fallbacks: dict[str, float],
    multiplier: float,
) -> float:
    """Get conservative fallback value for a rarity."""
    base = pack_fallbacks.get(rarity, GENERIC_FALLBACK_VALUES.get(rarity, 50.0))
    return base * multiplier
