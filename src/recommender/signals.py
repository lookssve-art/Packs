"""Signal detection — identifies odds shifts and significant changes."""

from __future__ import annotations

from src.models.dataclasses import DropRateSnapshot


def detect_odds_shift(
    old_snapshot: DropRateSnapshot | None,
    new_snapshot: DropRateSnapshot,
    threshold: float = 0.005,
) -> dict[str, float] | None:
    """Detect if drop rates have shifted between snapshots.

    Returns dict of rarity -> change amount if shift detected, None otherwise.
    Threshold is the minimum absolute change to consider significant.
    """
    if old_snapshot is None:
        return None

    if old_snapshot.pack_type != new_snapshot.pack_type:
        return None

    changes: dict[str, float] = {}
    all_rarities = set(old_snapshot.rates.keys()) | set(new_snapshot.rates.keys())

    for rarity in all_rarities:
        old_rate = old_snapshot.rates.get(rarity, 0.0)
        new_rate = new_snapshot.rates.get(rarity, 0.0)
        diff = new_rate - old_rate
        if abs(diff) >= threshold:
            changes[rarity] = diff

    return changes if changes else None


def detect_ev_change(
    old_ev_ratio: float,
    new_ev_ratio: float,
    threshold: float = 0.10,
) -> float | None:
    """Detect significant EV ratio change.

    Returns the change amount if significant, None otherwise.
    Threshold is relative change (0.10 = 10%).
    """
    if old_ev_ratio <= 0:
        return None

    relative_change = (new_ev_ratio - old_ev_ratio) / old_ev_ratio
    if abs(relative_change) >= threshold:
        return relative_change
    return None
