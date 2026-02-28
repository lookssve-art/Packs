"""Finite pool model for inventory-sensitive probability adjustment.

Only used when there is evidence that pulls are drawn from a finite
pool without replacement (pool mode). Default is IID mode.

This model layers hypergeometric adjustment on top of the Bayesian
posterior from the IID model.
"""

from __future__ import annotations

from src.models.iid_model import IIDModel


class PoolModel:
    """Adjusts probabilities based on remaining pool composition.

    If we know (or estimate) the pool started with N items per rarity,
    and K have been pulled, the remaining probability shifts.

    This is ONLY valid if:
    1. We can observe or infer pool composition
    2. There is evidence of no-replacement mechanics
    3. Restocks are detectable

    Usage is explicitly gated behind chi-squared test or manual override.
    """

    def __init__(
        self,
        initial_pool: dict[str, int] | None = None,
        iid_model: IIDModel | None = None,
    ):
        """Initialize pool model.

        Args:
            initial_pool: Estimated initial count per rarity in the pool.
                If None, pool mode is essentially disabled.
            iid_model: Underlying IID model for prior information.
        """
        self.initial_pool = initial_pool or {}
        self.iid_model = iid_model or IIDModel()

    def adjusted_probabilities(
        self,
        pulled_counts: dict[str, int],
    ) -> dict[str, float]:
        """Compute adjusted probabilities based on remaining pool.

        If initial_pool is not set, returns IID posterior means.
        """
        if not self.initial_pool:
            # No pool info — fall back to IID
            return self.iid_model.posterior_means(
                {r: float(c) for r, c in pulled_counts.items()}
            )

        remaining: dict[str, int] = {}
        for rarity, initial in self.initial_pool.items():
            pulled = pulled_counts.get(rarity, 0)
            remaining[rarity] = max(0, initial - pulled)

        total_remaining = sum(remaining.values())
        if total_remaining == 0:
            # Pool depleted — equal probability or signal restock needed
            n = len(remaining)
            return {r: 1.0 / n for r in remaining} if n > 0 else {}

        return {
            rarity: count / total_remaining
            for rarity, count in remaining.items()
        }

    def detect_restock(
        self,
        pulled_counts: dict[str, int],
        threshold_ratio: float = 0.9,
    ) -> bool:
        """Detect if a restock may have occurred.

        If total pulled exceeds threshold_ratio * total_initial,
        a restock is likely needed or has occurred.
        """
        if not self.initial_pool:
            return False

        total_initial = sum(self.initial_pool.values())
        total_pulled = sum(pulled_counts.values())

        return total_pulled >= total_initial * threshold_ratio
