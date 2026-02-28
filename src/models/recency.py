"""Exponential decay recency weighting for time-sensitive analysis."""

from __future__ import annotations

import datetime
import math
from collections import defaultdict

from src.models.dataclasses import Pull


def exponential_weight(
    timestamp: datetime.datetime,
    now: datetime.datetime,
    half_life_hours: float = 24.0,
) -> float:
    """Compute exponential decay weight for a timestamp.

    weight = exp(-ln(2) / half_life * age_hours)
    At age=0: weight=1.0, at age=half_life: weight=0.5
    """
    age_seconds = max(0.0, (now - timestamp).total_seconds())
    age_hours = age_seconds / 3600.0
    lam = math.log(2) / half_life_hours
    return math.exp(-lam * age_hours)


def weighted_rarity_counts(
    pulls: list[Pull],
    now: datetime.datetime | None = None,
    half_life_hours: float = 24.0,
) -> dict[str, float]:
    """Compute weighted observation counts per rarity tier.

    Each pull contributes its decay weight to its rarity bucket.
    """
    if now is None:
        now = datetime.datetime.utcnow()

    counts: dict[str, float] = defaultdict(float)
    for pull in pulls:
        w = exponential_weight(pull.timestamp, now, half_life_hours)
        counts[pull.rarity] += w
    return dict(counts)


def weighted_values_by_rarity(
    pulls: list[Pull],
    now: datetime.datetime | None = None,
    half_life_hours: float = 24.0,
) -> dict[str, list[tuple[float, float]]]:
    """Get (value, weight) pairs grouped by rarity for calibration.

    Uses payout_value if available, else estimated_value. Skips pulls
    with no value data.
    """
    if now is None:
        now = datetime.datetime.utcnow()

    result: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for pull in pulls:
        value = pull.payout_value or pull.estimated_value
        if value is None or value <= 0:
            continue
        w = exponential_weight(pull.timestamp, now, half_life_hours)
        result[pull.rarity].append((value, w))
    return dict(result)
