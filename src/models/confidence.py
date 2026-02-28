"""Confidence tier assignment based on observation counts."""

from __future__ import annotations

from config.constants import (
    CONFIDENCE_CALIBRATED,
    CONFIDENCE_PARTIAL,
    CONFIDENCE_VERY_CONSERVATIVE,
)


def get_confidence_tier(
    obs_count: int,
    threshold_partial: int = 3,
    threshold_calibrated: int = 10,
) -> str:
    """Determine confidence tier based on observation count.

    - < threshold_partial: very_conservative (aggressive haircut)
    - threshold_partial to threshold_calibrated: partial
    - >= threshold_calibrated: fully calibrated
    """
    if obs_count < threshold_partial:
        return CONFIDENCE_VERY_CONSERVATIVE
    elif obs_count < threshold_calibrated:
        return CONFIDENCE_PARTIAL
    return CONFIDENCE_CALIBRATED


def get_haircut(confidence_tier: str) -> float:
    """Get the EV multiplier (haircut) for a confidence tier.

    Lower confidence → more conservative (lower) EV estimate.
    """
    haircuts = {
        CONFIDENCE_VERY_CONSERVATIVE: 0.70,
        CONFIDENCE_PARTIAL: 0.85,
        CONFIDENCE_CALIBRATED: 1.00,
    }
    return haircuts.get(confidence_tier, 0.70)


def rarity_confidence_tier(
    rarity_obs_counts: dict[str, int],
    threshold_partial: int = 3,
    threshold_calibrated: int = 10,
) -> dict[str, str]:
    """Get confidence tier per rarity based on observation counts."""
    return {
        rarity: get_confidence_tier(count, threshold_partial, threshold_calibrated)
        for rarity, count in rarity_obs_counts.items()
    }
