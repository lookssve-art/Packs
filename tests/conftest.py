"""Shared test fixtures."""

from __future__ import annotations

import datetime
import sqlite3

import pytest

from src.models.dataclasses import (
    Alert,
    DropRateSnapshot,
    EVResult,
    PackTypeInfo,
    Pull,
)
from src.storage.database import init_db


@pytest.fixture
def in_memory_db():
    """Create an in-memory SQLite database with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    yield conn
    conn.close()


@pytest.fixture
def sample_pulls() -> list[Pull]:
    """Generate 50 sample pulls with realistic distribution."""
    pulls = []
    now = datetime.datetime.utcnow()
    rarity_dist = (
        [("holographic", 800.0)] * 2
        + [("gold", 150.0)] * 5
        + [("silver", 55.0)] * 18
        + [("gloss", 35.0)] * 25
    )

    for i, (rarity, value) in enumerate(rarity_dist):
        pulls.append(Pull(
            pull_id=f"test_pull_{i:04d}",
            timestamp=now - datetime.timedelta(hours=i * 0.5),
            pack_type="sapphire",
            rarity=rarity,
            card_name=f"Test Card {i}",
            estimated_value=value + (i % 10) * 5,
            payout_value=value * 0.85,
            source="test",
        ))
    return pulls


@pytest.fixture
def sample_emerald_pulls() -> list[Pull]:
    """Generate sample pulls for emerald pack."""
    pulls = []
    now = datetime.datetime.utcnow()
    rarity_dist = (
        [("holographic", 4000.0)] * 1
        + [("gold", 600.0)] * 3
        + [("silver", 220.0)] * 10
        + [("gloss", 160.0)] * 16
    )

    for i, (rarity, value) in enumerate(rarity_dist):
        pulls.append(Pull(
            pull_id=f"emerald_pull_{i:04d}",
            timestamp=now - datetime.timedelta(hours=i * 0.5),
            pack_type="emerald",
            rarity=rarity,
            card_name=f"Emerald Card {i}",
            estimated_value=value + (i % 5) * 20,
            payout_value=value * 0.90,
            source="test",
        ))
    return pulls


@pytest.fixture
def sample_drop_rates() -> dict[str, float]:
    """Sample published drop rates."""
    return {
        "holographic": 0.02,
        "gold": 0.08,
        "silver": 0.30,
        "gloss": 0.60,
    }


@pytest.fixture
def sample_pack_types() -> list[PackTypeInfo]:
    """Sample pack type info."""
    return [
        PackTypeInfo(
            slug="sapphire",
            display_name="Sapphire",
            cost_usd=50.0,
            sellback_rate=0.85,
        ),
        PackTypeInfo(
            slug="emerald",
            display_name="Emerald",
            cost_usd=250.0,
            sellback_rate=0.90,
        ),
    ]
