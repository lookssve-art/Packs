"""Tests for EV calculator."""

import datetime
import pytest

from src.models.dataclasses import PackTypeInfo, Pull
from src.models.ev_calculator import compute_ev, compute_all_evs


class TestEVCalculator:
    def test_compute_ev_basic(self, sample_pulls, sample_drop_rates):
        """Basic EV computation should produce reasonable results."""
        ev = compute_ev(
            pulls=sample_pulls,
            pack_type="sapphire",
            pack_cost=50.0,
            published_rates=sample_drop_rates,
        )

        assert ev.pack_type == "sapphire"
        assert ev.pack_cost == 50.0
        assert ev.ev > 0
        assert ev.ev_ratio > 0
        assert ev.obs_count == len(sample_pulls)
        assert ev.model_mode == "iid"

    def test_ev_with_no_pulls(self):
        """EV with no observations should use prior only."""
        ev = compute_ev(
            pulls=[],
            pack_type="sapphire",
            pack_cost=50.0,
        )
        assert ev.obs_count == 0
        assert ev.confidence_tier == "very_conservative"
        assert ev.ev >= 0

    def test_ev_ratio_calculation(self, sample_pulls):
        """EV ratio should be EV / cost."""
        ev = compute_ev(
            pulls=sample_pulls,
            pack_type="sapphire",
            pack_cost=50.0,
        )
        # With haircut applied, ev_ratio = (ev_raw * haircut) / cost
        # Just check it's positive and finite
        assert 0 < ev.ev_ratio < 100

    def test_rare_plus_probability(self, sample_pulls, sample_drop_rates):
        """P(rare+) should be between 0 and 1."""
        ev = compute_ev(
            pulls=sample_pulls,
            pack_type="sapphire",
            pack_cost=50.0,
            published_rates=sample_drop_rates,
        )
        assert 0.0 <= ev.p_rare_plus <= 1.0
        assert 0.0 <= ev.p_super_rare <= 1.0
        assert ev.p_rare_plus >= ev.p_super_rare

    def test_compute_all_evs(self, sample_pulls, sample_pack_types):
        """compute_all_evs should return results for all pack types."""
        results = compute_all_evs(
            all_pulls=sample_pulls,
            pack_types=sample_pack_types,
        )
        assert len(results) == 2  # sapphire + emerald

        pack_types_returned = {r.pack_type for r in results}
        assert "sapphire" in pack_types_returned
        assert "emerald" in pack_types_returned

    def test_confidence_tiers(self):
        """Confidence should scale with observation count."""
        now = datetime.datetime.utcnow()

        # Few pulls — very conservative
        few_pulls = [
            Pull(
                pull_id=f"few_{i}",
                timestamp=now,
                pack_type="sapphire",
                rarity="gloss",
                estimated_value=35.0,
                source="test",
            )
            for i in range(2)
        ]
        ev_few = compute_ev(few_pulls, "sapphire", 50.0)
        assert ev_few.confidence_tier == "very_conservative"

        # Some pulls — partial
        some_pulls = [
            Pull(
                pull_id=f"some_{i}",
                timestamp=now,
                pack_type="sapphire",
                rarity="gloss",
                estimated_value=35.0,
                source="test",
            )
            for i in range(5)
        ]
        ev_some = compute_ev(some_pulls, "sapphire", 50.0)
        assert ev_some.confidence_tier == "partial"

        # Many pulls — calibrated
        many_pulls = [
            Pull(
                pull_id=f"many_{i}",
                timestamp=now,
                pack_type="sapphire",
                rarity="gloss",
                estimated_value=35.0,
                source="test",
            )
            for i in range(15)
        ]
        ev_many = compute_ev(many_pulls, "sapphire", 50.0)
        assert ev_many.confidence_tier == "calibrated"
