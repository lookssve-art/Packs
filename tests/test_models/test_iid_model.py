"""Tests for the Dirichlet-Multinomial IID model."""

import numpy as np
import pytest

from src.models.iid_model import IIDModel


class TestIIDModel:
    def test_uninformative_prior(self):
        """With no published rates, prior should be uniform."""
        model = IIDModel()
        means = model.posterior_means({})
        # With uniform prior and no observations, means should be equal
        values = list(means.values())
        assert all(abs(v - values[0]) < 0.01 for v in values)

    def test_prior_from_published_rates(self):
        """Prior should reflect published rates."""
        rates = {"holographic": 0.02, "gold": 0.08, "silver": 0.30, "gloss": 0.60}
        model = IIDModel(published_rates=rates, prior_strength=100.0)

        # With no observations and strong prior, means should match rates
        means = model.posterior_means({})
        for rarity, rate in rates.items():
            assert abs(means[rarity] - rate) < 0.01, (
                f"{rarity}: expected ~{rate}, got {means[rarity]}"
            )

    def test_posterior_update(self):
        """Posterior should move toward observations."""
        rates = {"holographic": 0.02, "gold": 0.08, "silver": 0.30, "gloss": 0.60}
        model = IIDModel(published_rates=rates, prior_strength=5.0)

        # Observe many gold hits
        counts = {"holographic": 0.0, "gold": 50.0, "silver": 10.0, "gloss": 5.0}
        means = model.posterior_means(counts)

        # Gold should be much higher than published rate
        assert means["gold"] > rates["gold"]
        # Gold should dominate with these counts
        assert means["gold"] > 0.5

    def test_credible_intervals_contain_mean(self):
        """Credible interval should contain the mean."""
        model = IIDModel()
        counts = {"holographic": 2.0, "gold": 8.0, "silver": 30.0, "gloss": 60.0}
        intervals = model.credible_intervals(counts, ci_level=0.90)

        for rarity, (mean, lower, upper) in intervals.items():
            assert lower <= mean <= upper, (
                f"{rarity}: {lower} <= {mean} <= {upper}"
            )
            assert lower >= 0.0
            assert upper <= 1.0

    def test_p_rare_plus(self):
        """P(rare+) should be sum of holographic and gold."""
        model = IIDModel()
        counts = {"holographic": 2.0, "gold": 8.0, "silver": 30.0, "gloss": 60.0}
        means = model.posterior_means(counts)
        p_rare = model.p_rare_plus(counts)
        assert abs(p_rare - means["holographic"] - means["gold"]) < 0.001

    def test_p_super_rare(self):
        """P(super rare) should equal holographic probability."""
        model = IIDModel()
        counts = {"holographic": 5.0, "gold": 5.0, "silver": 5.0, "gloss": 5.0}
        means = model.posterior_means(counts)
        assert abs(model.p_super_rare(counts) - means["holographic"]) < 0.001

    def test_chi_squared_test_matching(self):
        """Chi-squared test should not reject matching rates."""
        rates = {"holographic": 0.02, "gold": 0.08, "silver": 0.30, "gloss": 0.60}
        model = IIDModel(published_rates=rates)

        # Observations that closely match published rates
        obs = {"holographic": 2, "gold": 8, "silver": 30, "gloss": 60}
        chi2, p = model.chi_squared_test(obs, rates)
        assert p > 0.05  # Should not reject

    def test_chi_squared_test_divergent(self):
        """Chi-squared test should reject very divergent rates."""
        rates = {"holographic": 0.02, "gold": 0.08, "silver": 0.30, "gloss": 0.60}
        model = IIDModel(published_rates=rates)

        # Observations that deviate wildly
        obs = {"holographic": 30, "gold": 30, "silver": 30, "gloss": 10}
        chi2, p = model.chi_squared_test(obs, rates)
        assert p < 0.01  # Should reject

    def test_zero_observations(self):
        """Model should gracefully handle zero observations."""
        model = IIDModel()
        means = model.posterior_means({})
        assert sum(means.values()) == pytest.approx(1.0, abs=0.01)

        intervals = model.credible_intervals({})
        for rarity, (mean, lower, upper) in intervals.items():
            assert lower <= mean <= upper
