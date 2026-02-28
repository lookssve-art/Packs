"""Dirichlet-Multinomial Bayesian model for IID pack rips.

Uses conjugate Dirichlet prior with observed (weighted) rarity counts
to compute posterior probabilities and credible intervals.
No MCMC needed — exact conjugate update.
"""

from __future__ import annotations

import numpy as np
from scipy import stats

from config.constants import RARITY_ORDER, UNINFORMATIVE_PRIOR


class IIDModel:
    """Bayesian IID model using Dirichlet-Multinomial conjugacy.

    Prior: Dirichlet(alpha_0) where alpha_0 is derived from published
    drop rates (if available) scaled by prior_strength.

    Posterior: Dirichlet(alpha_0 + weighted_counts).
    """

    def __init__(
        self,
        published_rates: dict[str, float] | None = None,
        prior_strength: float = 5.0,
        rarity_order: list[str] | None = None,
    ):
        self.rarity_order = rarity_order or RARITY_ORDER
        self.n_categories = len(self.rarity_order)

        if published_rates:
            # Build prior from published rates
            rates_array = np.array([
                published_rates.get(r, 1.0 / self.n_categories)
                for r in self.rarity_order
            ])
            # Normalize to ensure sum = 1
            rates_array = rates_array / rates_array.sum()
            self.alpha_prior = rates_array * prior_strength
        else:
            # Uninformative prior
            self.alpha_prior = np.array(
                UNINFORMATIVE_PRIOR[:self.n_categories], dtype=float
            )

    def compute_posterior(
        self, weighted_counts: dict[str, float]
    ) -> np.ndarray:
        """Compute posterior Dirichlet parameters.

        alpha_post = alpha_prior + observed_weighted_counts
        """
        counts = np.array([
            weighted_counts.get(r, 0.0) for r in self.rarity_order
        ])
        return self.alpha_prior + counts

    def posterior_means(
        self, weighted_counts: dict[str, float]
    ) -> dict[str, float]:
        """Compute posterior mean probability for each rarity."""
        alpha_post = self.compute_posterior(weighted_counts)
        total = alpha_post.sum()
        means = alpha_post / total
        return {
            r: float(means[i])
            for i, r in enumerate(self.rarity_order)
        }

    def credible_intervals(
        self,
        weighted_counts: dict[str, float],
        ci_level: float = 0.90,
    ) -> dict[str, tuple[float, float, float]]:
        """Compute posterior mean and credible interval for each rarity.

        Each component of Dirichlet is marginally Beta-distributed:
        p_i ~ Beta(alpha_i, sum(alpha) - alpha_i)

        Returns dict of rarity -> (mean, lower, upper)
        """
        alpha_post = self.compute_posterior(weighted_counts)
        total = alpha_post.sum()
        tail = (1.0 - ci_level) / 2.0

        result = {}
        for i, rarity in enumerate(self.rarity_order):
            a = alpha_post[i]
            b = total - a
            mean = float(a / total)
            lower = float(stats.beta.ppf(tail, a, b))
            upper = float(stats.beta.ppf(1.0 - tail, a, b))
            result[rarity] = (mean, lower, upper)
        return result

    def p_rare_plus(
        self, weighted_counts: dict[str, float]
    ) -> float:
        """P(holographic or gold) — posterior mean."""
        means = self.posterior_means(weighted_counts)
        rare_rarities = {"holographic", "gold"}
        return sum(
            v for k, v in means.items() if k in rare_rarities
        )

    def p_super_rare(
        self, weighted_counts: dict[str, float]
    ) -> float:
        """P(holographic) — posterior mean."""
        means = self.posterior_means(weighted_counts)
        return means.get("holographic", 0.0)

    def conservative_p_rare_plus(
        self, weighted_counts: dict[str, float], ci_level: float = 0.90
    ) -> float:
        """Lower bound of P(rare+) using lower credible interval."""
        intervals = self.credible_intervals(weighted_counts, ci_level)
        rare_rarities = {"holographic", "gold"}
        return sum(
            intervals[r][1]  # lower bound
            for r in rare_rarities
            if r in intervals
        )

    def chi_squared_test(
        self,
        observed_counts: dict[str, int],
        published_rates: dict[str, float] | None = None,
    ) -> tuple[float, float]:
        """Chi-squared goodness-of-fit test against published rates.

        Returns (chi2_statistic, p_value).
        If p_value < threshold, rates may not be IID with published rates.
        """
        if published_rates is None:
            # Use prior means
            total_alpha = self.alpha_prior.sum()
            expected_rates = self.alpha_prior / total_alpha
        else:
            expected_rates = np.array([
                published_rates.get(r, 1.0 / self.n_categories)
                for r in self.rarity_order
            ])
            expected_rates = expected_rates / expected_rates.sum()

        observed = np.array([
            observed_counts.get(r, 0) for r in self.rarity_order
        ])
        total_obs = observed.sum()
        if total_obs == 0:
            return 0.0, 1.0

        expected = expected_rates * total_obs
        # Avoid division by zero
        mask = expected > 0
        if not mask.any():
            return 0.0, 1.0

        chi2 = float(np.sum((observed[mask] - expected[mask]) ** 2 / expected[mask]))
        df = int(mask.sum()) - 1
        if df <= 0:
            return chi2, 1.0
        p_value = float(1.0 - stats.chi2.cdf(chi2, df))
        return chi2, p_value
