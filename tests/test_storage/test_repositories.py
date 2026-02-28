"""Tests for CRUD repositories."""

import datetime
import pytest

from src.models.dataclasses import Alert, DropRateSnapshot, PackTypeInfo, Pull
from src.storage.repositories import (
    AlertRepository,
    PackTypeRepository,
    PullRepository,
    SnapshotRepository,
)


class TestPullRepository:
    def test_insert_and_retrieve(self, in_memory_db):
        repo = PullRepository(in_memory_db)
        pull = Pull(
            pull_id="test_001",
            timestamp=datetime.datetime.utcnow(),
            pack_type="sapphire",
            rarity="gold",
            estimated_value=150.0,
            source="test",
        )
        assert repo.insert(pull) is True

        recent = repo.get_recent(limit=10)
        assert len(recent) == 1
        assert recent[0].pull_id == "test_001"
        assert recent[0].rarity == "gold"

    def test_deduplication(self, in_memory_db):
        repo = PullRepository(in_memory_db)
        pull = Pull(
            pull_id="dup_001",
            timestamp=datetime.datetime.utcnow(),
            pack_type="sapphire",
            rarity="silver",
            source="test",
        )
        assert repo.insert(pull) is True
        assert repo.insert(pull) is False  # Duplicate

        recent = repo.get_recent(limit=10)
        assert len(recent) == 1

    def test_batch_insert(self, in_memory_db, sample_pulls):
        repo = PullRepository(in_memory_db)
        inserted = repo.insert_batch(sample_pulls)
        assert inserted == len(sample_pulls)

        # Insert same batch again — should all be dupes
        inserted_again = repo.insert_batch(sample_pulls)
        assert inserted_again == 0

    def test_filter_by_pack_type(self, in_memory_db, sample_pulls):
        repo = PullRepository(in_memory_db)
        repo.insert_batch(sample_pulls)

        sapphire = repo.get_recent(pack_type="sapphire")
        assert len(sapphire) == len(sample_pulls)

        emerald = repo.get_recent(pack_type="emerald")
        assert len(emerald) == 0

    def test_get_count_by_pack(self, in_memory_db, sample_pulls):
        repo = PullRepository(in_memory_db)
        repo.insert_batch(sample_pulls)

        counts = repo.get_count_by_pack()
        assert counts["sapphire"] == len(sample_pulls)


class TestSnapshotRepository:
    def test_insert_and_get_latest(self, in_memory_db):
        repo = SnapshotRepository(in_memory_db)
        snapshot = DropRateSnapshot(
            timestamp=datetime.datetime.utcnow(),
            pack_type="sapphire",
            rates={"holographic": 0.02, "gold": 0.08, "silver": 0.30, "gloss": 0.60},
            source="test",
        )
        repo.insert(snapshot)

        latest = repo.get_latest("sapphire")
        assert latest is not None
        assert latest.rates["holographic"] == 0.02

    def test_has_rates_changed(self, in_memory_db):
        repo = SnapshotRepository(in_memory_db)
        rates = {"holographic": 0.02, "gold": 0.08, "silver": 0.30, "gloss": 0.60}
        snapshot = DropRateSnapshot(
            timestamp=datetime.datetime.utcnow(),
            pack_type="sapphire",
            rates=rates,
            source="test",
        )
        repo.insert(snapshot)

        # Same rates — no change
        assert repo.has_rates_changed("sapphire", rates) is False

        # Different rates — change detected
        new_rates = dict(rates)
        new_rates["holographic"] = 0.03
        assert repo.has_rates_changed("sapphire", new_rates) is True


class TestPackTypeRepository:
    def test_upsert_and_retrieve(self, in_memory_db):
        repo = PackTypeRepository(in_memory_db)
        pack = PackTypeInfo(
            slug="sapphire",
            display_name="Sapphire",
            cost_usd=50.0,
            sellback_rate=0.85,
        )
        repo.upsert(pack)

        result = repo.get_by_slug("sapphire")
        assert result is not None
        assert result.cost_usd == 50.0
        assert result.sellback_rate == 0.85

    def test_upsert_updates_existing(self, in_memory_db):
        repo = PackTypeRepository(in_memory_db)
        pack = PackTypeInfo(slug="test", display_name="Test", cost_usd=50.0)
        repo.upsert(pack)

        # Update cost
        pack2 = PackTypeInfo(slug="test", display_name="Test Updated", cost_usd=75.0)
        repo.upsert(pack2)

        result = repo.get_by_slug("test")
        assert result.cost_usd == 75.0
        assert result.display_name == "Test Updated"

    def test_get_all_active(self, in_memory_db):
        repo = PackTypeRepository(in_memory_db)
        repo.upsert(PackTypeInfo(slug="a", display_name="A", cost_usd=50.0))
        repo.upsert(PackTypeInfo(slug="b", display_name="B", cost_usd=250.0))

        active = repo.get_all_active()
        assert len(active) == 2


class TestAlertRepository:
    def test_insert_and_get_active(self, in_memory_db):
        repo = AlertRepository(in_memory_db)
        alert = Alert(
            timestamp=datetime.datetime.utcnow(),
            alert_type="ev_ratio_above_1",
            pack_type="sapphire",
            severity="warning",
            message="Test alert",
        )
        repo.insert(alert)

        active = repo.get_active()
        assert len(active) == 1
        assert active[0].message == "Test alert"

    def test_acknowledge(self, in_memory_db):
        repo = AlertRepository(in_memory_db)
        alert = Alert(
            timestamp=datetime.datetime.utcnow(),
            alert_type="test",
            pack_type="sapphire",
            severity="info",
            message="Ack test",
        )
        alert_id = repo.insert(alert)
        repo.acknowledge(alert_id)

        active = repo.get_active()
        assert len(active) == 0
