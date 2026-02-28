"""Pack ranking engine — ranks packs across 4 modes.

1. Best Rare+ chance (P(epic or rare))
2. Best Super Rare chance (P(epic))
3. Best EV Ratio
4. Conservative score
"""

from __future__ import annotations

from dataclasses import dataclass

from src.models.dataclasses import EVResult


@dataclass
class RankedPack:
    """A pack with its rank and score for a specific ranking mode."""
    rank: int
    pack_type: str
    score: float
    label: str
    confidence_tier: str
    ev_result: EVResult


def rank_by_rare_plus(ev_results: list[EVResult]) -> list[RankedPack]:
    """Rank packs by P(Rare+) = P(epic or rare)."""
    sorted_results = sorted(ev_results, key=lambda e: e.p_rare_plus, reverse=True)
    return [
        RankedPack(
            rank=i + 1,
            pack_type=ev.pack_type,
            score=ev.p_rare_plus,
            label=f"{ev.p_rare_plus * 100:.2f}%",
            confidence_tier=ev.confidence_tier,
            ev_result=ev,
        )
        for i, ev in enumerate(sorted_results)
    ]


def rank_by_super_rare(ev_results: list[EVResult]) -> list[RankedPack]:
    """Rank packs by P(Super Rare) = P(epic)."""
    sorted_results = sorted(ev_results, key=lambda e: e.p_super_rare, reverse=True)
    return [
        RankedPack(
            rank=i + 1,
            pack_type=ev.pack_type,
            score=ev.p_super_rare,
            label=f"{ev.p_super_rare * 100:.2f}%",
            confidence_tier=ev.confidence_tier,
            ev_result=ev,
        )
        for i, ev in enumerate(sorted_results)
    ]


def rank_by_ev_ratio(ev_results: list[EVResult]) -> list[RankedPack]:
    """Rank packs by EV Ratio (EV / cost)."""
    sorted_results = sorted(ev_results, key=lambda e: e.ev_ratio, reverse=True)
    return [
        RankedPack(
            rank=i + 1,
            pack_type=ev.pack_type,
            score=ev.ev_ratio,
            label=f"{ev.ev_ratio:.3f}",
            confidence_tier=ev.confidence_tier,
            ev_result=ev,
        )
        for i, ev in enumerate(sorted_results)
    ]


def rank_by_conservative_score(ev_results: list[EVResult]) -> list[RankedPack]:
    """Rank packs by conservative EV ratio (lower confidence bound)."""
    sorted_results = sorted(
        ev_results, key=lambda e: e.conservative_score, reverse=True
    )
    return [
        RankedPack(
            rank=i + 1,
            pack_type=ev.pack_type,
            score=ev.conservative_score,
            label=f"{ev.conservative_score:.3f}",
            confidence_tier=ev.confidence_tier,
            ev_result=ev,
        )
        for i, ev in enumerate(sorted_results)
    ]


def get_all_rankings(
    ev_results: list[EVResult],
) -> dict[str, list[RankedPack]]:
    """Compute all ranking modes at once."""
    return {
        "rare_plus": rank_by_rare_plus(ev_results),
        "super_rare": rank_by_super_rare(ev_results),
        "ev_ratio": rank_by_ev_ratio(ev_results),
        "conservative": rank_by_conservative_score(ev_results),
    }
