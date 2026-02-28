"""Tests for recency weighting."""

import datetime
import math
import pytest

from src.models.dataclasses import Pull
from src.models.recency import (
    exponential_weight,
    weighted_rarity_counts,
    weighted_values_by_rarity,
)


class TestExponentialWeight:
    def test_weight_at_zero(self):
        """Weight at t=0 should be 1.0."""
        now = datetime.datetime.utcnow()
        w = exponential_weight(now, now)
        assert w == pytest.approx(1.0)

    def test_weight_at_half_life(self):
        """Weight at t=half_life should be 0.5."""
        now = datetime.datetime.utcnow()
        past = now - datetime.timedelta(hours=24)
        w = exponential_weight(past, now, half_life_hours=24.0)
        assert w == pytest.approx(0.5, abs=0.001)

    def test_weight_at_double_half_life(self):
        """Weight at t=2*half_life should be 0.25."""
        now = datetime.datetime.utcnow()
        past = now - datetime.timedelta(hours=48)
        w = exponential_weight(past, now, half_life_hours=24.0)
        assert w == pytest.approx(0.25, abs=0.001)

    def test_weight_monotonically_decreasing(self):
        """Weights should decrease as age increases."""
        now = datetime.datetime.utcnow()
        weights = []
        for hours in [0, 1, 6, 12, 24, 48, 72]:
            past = now - datetime.timedelta(hours=hours)
            weights.append(exponential_weight(past, now))
        for i in range(len(weights) - 1):
            assert weights[i] >= weights[i + 1]

    def test_future_timestamp_clamps_to_1(self):
        """Future timestamps should have weight 1.0."""
        now = datetime.datetime.utcnow()
        future = now + datetime.timedelta(hours=1)
        w = exponential_weight(future, now)
        assert w == pytest.approx(1.0)


class TestWeightedRarityCounts:
    def test_recent_pulls_weighted_higher(self):
        """More recent pulls should contribute more weight."""
        now = datetime.datetime.utcnow()
        pulls = [
            Pull(pull_id="old", timestamp=now - datetime.timedelta(hours=48),
                 pack_type="sapphire", rarity="gold", source="test"),
            Pull(pull_id="new", timestamp=now,
                 pack_type="sapphire", rarity="gold", source="test"),
        ]
        counts = weighted_rarity_counts(pulls, now, half_life_hours=24.0)
        # Weight of new: 1.0, weight of old: 0.25
        assert counts["gold"] == pytest.approx(1.25, abs=0.01)

    def test_empty_pulls(self):
        """Empty pulls should return empty counts."""
        counts = weighted_rarity_counts([])
        assert counts == {}
