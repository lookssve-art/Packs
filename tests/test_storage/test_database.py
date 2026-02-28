"""Tests for database initialization and schema."""

import sqlite3
import pytest
from src.storage.database import init_db


def test_init_db_creates_tables(in_memory_db):
    """Verify all tables are created."""
    cursor = in_memory_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = {row["name"] for row in cursor.fetchall()}

    expected_tables = {
        "pulls",
        "drop_rate_snapshots",
        "raw_responses",
        "ev_snapshots",
        "alerts",
        "discovered_endpoints",
        "pack_types",
    }
    assert expected_tables.issubset(tables)


def test_init_db_is_idempotent(in_memory_db):
    """Calling init_db twice should not error."""
    init_db(in_memory_db)  # Second call
    cursor = in_memory_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    tables = cursor.fetchall()
    assert len(tables) > 0


def test_pulls_table_has_correct_columns(in_memory_db):
    """Verify pulls table schema."""
    cursor = in_memory_db.execute("PRAGMA table_info(pulls)")
    columns = {row["name"] for row in cursor.fetchall()}
    assert "pull_id" in columns
    assert "timestamp" in columns
    assert "pack_type" in columns
    assert "rarity" in columns
    assert "estimated_value" in columns
    assert "payout_value" in columns
