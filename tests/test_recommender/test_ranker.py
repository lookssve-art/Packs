"""Tests for pack ranker."""

import pytest

from src.models.dataclasses import EVResult
from src.recommender.ranker import (
    get_all_rankings,
    rank_by_ev_ratio,
    rank_by_rare_plus,
    rank_by_super_rare,
)


@pytest.fixture
def mock_ev_results() -> list[EVResult]:
    return [
        EVResult(
            pack_type="sapphire",
            ev=48.0,
            ev_ratio=0.96,
            pack_cost=50.0,
            confidence_tier="calibrated",
            obs_count=100,
            rarity_posteriors={
                "holographic": (0.02, 0.01, 0.04),
                "gold": (0.08, 0.05, 0.12),
                "silver": (0.30, 0.24, 0.36),
                "gloss": (0.60, 0.52, 0.68),
            },
            calibrated_values={"holographic": 800, "gold": 150, "silver": 55, "gloss": 35},
            model_mode="iid",
            p_rare_plus=0.10,
            p_super_rare=0.02,
            conservative_score=0.85,
        ),
        EVResult(
            pack_type="emerald",
            ev=260.0,
            ev_ratio=1.04,
            pack_cost=250.0,
            confidence_tier="partial",
            obs_count=30,
            rarity_posteriors={
                "holographic": (0.03, 0.01, 0.06),
                "gold": (0.10, 0.06, 0.15),
                "silver": (0.35, 0.28, 0.42),
                "gloss": (0.52, 0.44, 0.60),
            },
            calibrated_values={"holographic": 4000, "gold": 600, "silver": 220, "gloss": 160},
            model_mode="iid",
            p_rare_plus=0.13,
            p_super_rare=0.03,
            conservative_score=0.92,
        ),
    ]


class TestRanker:
    def test_rank_by_rare_plus(self, mock_ev_results):
        ranked = rank_by_rare_plus(mock_ev_results)
        assert len(ranked) == 2
        assert ranked[0].pack_type == "emerald"  # 0.13 > 0.10
        assert ranked[0].rank == 1

    def test_rank_by_super_rare(self, mock_ev_results):
        ranked = rank_by_super_rare(mock_ev_results)
        assert ranked[0].pack_type == "emerald"  # 0.03 > 0.02
        assert ranked[0].rank == 1

    def test_rank_by_ev_ratio(self, mock_ev_results):
        ranked = rank_by_ev_ratio(mock_ev_results)
        assert ranked[0].pack_type == "emerald"  # 1.04 > 0.96
        assert ranked[0].rank == 1

    def test_get_all_rankings(self, mock_ev_results):
        rankings = get_all_rankings(mock_ev_results)
        assert "rare_plus" in rankings
        assert "super_rare" in rankings
        assert "ev_ratio" in rankings
        assert "conservative" in rankings
        for key, ranked in rankings.items():
            assert len(ranked) == 2

    def test_empty_results(self):
        ranked = rank_by_ev_ratio([])
        assert ranked == []
