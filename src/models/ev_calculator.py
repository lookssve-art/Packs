"""EV (Expected Value) and EV Ratio calculator.

EV = sum(P(rarity_i) * calibrated_value(rarity_i))
EV_Ratio = EV / pack_cost
"""

from __future__ import annotations

import datetime

from config.constants import COLLECTION_PACK_MAP, KNOWN_PACKS, RARITY_ORDER
from src.models.confidence import get_confidence_tier, get_haircut
from src.models.dataclasses import EVResult, PackTypeInfo, Pull
from src.models.iid_model import IIDModel
from src.models.recency import weighted_rarity_counts, weighted_values_by_rarity
from src.models.value_model import calibrate_values_with_confidence


def compute_ev(
    pulls: list[Pull],
    pack_type: str,
    pack_cost: float,
    published_rates: dict[str, float] | None = None,
    half_life_hours: float = 24.0,
    prior_strength: float = 5.0,
    now: datetime.datetime | None = None,
) -> EVResult:
    """Compute full EV analysis for a pack type.

    Args:
        pulls: Recent pulls for this pack type
        pack_type: Pack slug
        pack_cost: Cost in USD
        published_rates: Official drop rates if known
        half_life_hours: Exponential decay half-life
        prior_strength: Strength of Bayesian prior
        now: Current time (default: utcnow)

    Returns:
        Complete EVResult with probabilities, values, and confidence
    """
    if now is None:
        now = datetime.datetime.utcnow()

    # 1. Get weighted rarity counts for probability estimation
    w_counts = weighted_rarity_counts(pulls, now, half_life_hours)

    # 2. Build Bayesian model and compute posteriors
    model = IIDModel(
        published_rates=published_rates,
        prior_strength=prior_strength,
    )
    posteriors = model.credible_intervals(w_counts)
    means = model.posterior_means(w_counts)

    # 3. Get weighted value observations for calibration
    value_pairs = weighted_values_by_rarity(pulls, now, half_life_hours)

    # 4. Calibrate values
    cal_values, val_tiers, val_counts = calibrate_values_with_confidence(
        value_pairs, pack_type
    )

    # 5. Overall observation count
    total_obs = len(pulls)
    overall_confidence = get_confidence_tier(total_obs)

    # 6. Compute raw EV
    all_rarities = set(means.keys()) | set(cal_values.keys())
    ev_raw = 0.0
    for rarity in all_rarities:
        p = means.get(rarity, 0.0)
        v = cal_values.get(rarity, 0.0)
        ev_raw += p * v

    # 7. Apply confidence haircut
    haircut = get_haircut(overall_confidence)
    ev = ev_raw * haircut
    ev_ratio = ev / pack_cost if pack_cost > 0 else 0.0

    # 8. Compute conservative score (lower bound of EV ratio)
    ev_conservative = 0.0
    for rarity in all_rarities:
        # Use lower CI bound for valuable rarities, upper for common
        if rarity in {"holographic", "gold"}:
            p = posteriors.get(rarity, (0.0, 0.0, 0.0))[1]  # lower bound
        else:
            p = posteriors.get(rarity, (0.0, 0.0, 0.0))[2]  # upper bound
        v = cal_values.get(rarity, 0.0)
        ev_conservative += p * v

    conservative_score = (ev_conservative * haircut / pack_cost
                          if pack_cost > 0 else 0.0)

    # 9. Rare+ and Super Rare probabilities
    p_rare_plus = model.p_rare_plus(w_counts)
    p_super_rare = model.p_super_rare(w_counts)

    return EVResult(
        pack_type=pack_type,
        ev=ev,
        ev_ratio=ev_ratio,
        pack_cost=pack_cost,
        confidence_tier=overall_confidence,
        obs_count=total_obs,
        rarity_posteriors=posteriors,
        calibrated_values=cal_values,
        model_mode="iid",
        p_rare_plus=p_rare_plus,
        p_super_rare=p_super_rare,
        conservative_score=conservative_score,
    )


def compute_all_evs(
    all_pulls: list[Pull],
    pack_types: list[PackTypeInfo],
    published_rates: dict[str, dict[str, float]] | None = None,
    half_life_hours: float = 24.0,
    prior_strength: float = 5.0,
    now: datetime.datetime | None = None,
) -> list[EVResult]:
    """Compute EV for all active pack types."""
    if now is None:
        now = datetime.datetime.utcnow()

    # Build reverse map: pack_slug -> set of collection symbols that feed it
    _pack_sources: dict[str, set[str]] = {}
    for coll, slugs in COLLECTION_PACK_MAP.items():
        for s in slugs:
            _pack_sources.setdefault(s, set()).add(coll)

    results = []
    for pack in pack_types:
        # Include pulls matching the pack slug OR any mapped collection
        sources = _pack_sources.get(pack.slug, set())
        pack_pulls = [
            p for p in all_pulls
            if p.pack_type == pack.slug or p.pack_type in sources
        ]
        rates = (published_rates or {}).get(pack.slug)
        ev = compute_ev(
            pulls=pack_pulls,
            pack_type=pack.slug,
            pack_cost=pack.cost_usd,
            published_rates=rates,
            half_life_hours=half_life_hours,
            prior_strength=prior_strength,
            now=now,
        )
        results.append(ev)
    return results
