"""Core data models for the pack tracking system."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Pull:
    """A single pack rip result."""
    pull_id: str
    timestamp: datetime.datetime
    pack_type: str  # dynamic slug, e.g. 'sapphire', 'emerald'
    rarity: str     # e.g. 'holographic', 'gold', 'silver', 'gloss'
    card_name: Optional[str] = None
    card_id: Optional[str] = None
    token_mint: Optional[str] = None
    value_bucket: Optional[str] = None
    estimated_value: Optional[float] = None
    payout_value: Optional[float] = None
    image_url: Optional[str] = None
    source: str = ""
    snapshot_id: Optional[int] = None


@dataclass
class DropRateSnapshot:
    """Observed drop rate table at a point in time."""
    timestamp: datetime.datetime
    pack_type: str
    rates: dict[str, float]  # rarity -> probability (0.0 to 1.0)
    source: str = ""
    id: Optional[int] = None


@dataclass
class PackTypeInfo:
    """Dynamically discovered pack type."""
    slug: str
    display_name: str
    cost_usd: float
    sellback_rate: Optional[float] = None
    rarity_tiers: list[str] = field(default_factory=lambda: [
        "holographic", "gold", "silver", "gloss"
    ])
    is_active: bool = True


@dataclass
class EVResult:
    """Expected value computation result for a pack type."""
    pack_type: str
    ev: float
    ev_ratio: float
    pack_cost: float
    confidence_tier: str
    obs_count: int
    rarity_posteriors: dict[str, tuple[float, float, float]]  # (mean, lower_5, upper_95)
    calibrated_values: dict[str, float]
    model_mode: str  # 'iid' or 'pool'
    p_rare_plus: float = 0.0      # P(gold or holographic)
    p_super_rare: float = 0.0     # P(holographic)
    conservative_score: float = 0.0  # lower confidence bound of EV ratio


@dataclass
class Alert:
    """Triggered alert."""
    timestamp: datetime.datetime
    alert_type: str
    pack_type: str
    severity: str  # 'info', 'warning', 'critical'
    message: str
    details: Optional[dict] = None
    acknowledged: bool = False
    id: Optional[int] = None
