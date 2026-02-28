"""SQLite database connection manager and schema initialization."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Generator


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS pulls (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pull_id         TEXT UNIQUE NOT NULL,
    timestamp       TEXT NOT NULL,
    pack_type       TEXT NOT NULL,
    card_name       TEXT,
    card_id         TEXT,
    token_mint      TEXT,
    rarity          TEXT NOT NULL,
    value_bucket    TEXT,
    estimated_value REAL,
    payout_value    REAL,
    image_url       TEXT,
    source          TEXT NOT NULL,
    snapshot_id     INTEGER,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_pulls_timestamp ON pulls(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_pulls_pack_type ON pulls(pack_type);
CREATE INDEX IF NOT EXISTS idx_pulls_rarity ON pulls(rarity);
CREATE INDEX IF NOT EXISTS idx_pulls_pack_rarity ON pulls(pack_type, rarity);

CREATE TABLE IF NOT EXISTS drop_rate_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,
    pack_type       TEXT NOT NULL,
    source          TEXT NOT NULL,
    rates_json      TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_snapshots_pack_time
    ON drop_rate_snapshots(pack_type, timestamp DESC);

CREATE TABLE IF NOT EXISTS raw_responses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,
    source          TEXT NOT NULL,
    endpoint        TEXT,
    request_params  TEXT,
    response_body   TEXT NOT NULL,
    http_status     INTEGER,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_raw_timestamp ON raw_responses(timestamp DESC);

CREATE TABLE IF NOT EXISTS ev_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,
    pack_type       TEXT NOT NULL,
    model_mode      TEXT NOT NULL,
    ev_value        REAL NOT NULL,
    ev_ratio        REAL NOT NULL,
    pack_cost       REAL NOT NULL,
    confidence_tier TEXT NOT NULL,
    obs_count       INTEGER NOT NULL,
    posterior_json  TEXT NOT NULL,
    bucket_values_json TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ev_pack_time
    ON ev_snapshots(pack_type, timestamp DESC);

CREATE TABLE IF NOT EXISTS alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,
    alert_type      TEXT NOT NULL,
    pack_type       TEXT NOT NULL,
    severity        TEXT NOT NULL,
    message         TEXT NOT NULL,
    details_json    TEXT,
    acknowledged    INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_alerts_time ON alerts(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type);

CREATE TABLE IF NOT EXISTS discovered_endpoints (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    url_pattern     TEXT NOT NULL,
    method          TEXT NOT NULL,
    description     TEXT,
    sample_params   TEXT,
    sample_response TEXT,
    discovered_at   TEXT NOT NULL,
    last_verified   TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS pack_types (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    slug            TEXT UNIQUE NOT NULL,
    display_name    TEXT NOT NULL,
    cost_usd        REAL NOT NULL,
    sellback_rate   REAL,
    rarity_tiers    TEXT NOT NULL,
    first_seen      TEXT NOT NULL,
    last_seen       TEXT NOT NULL,
    is_active       INTEGER NOT NULL DEFAULT 1
);
"""


def get_connection(db_path: str) -> sqlite3.Connection:
    """Create a new database connection with WAL mode for concurrent access."""
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes."""
    conn.executescript(SCHEMA_SQL)
    conn.commit()


@contextmanager
def get_db(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for database connections."""
    conn = get_connection(db_path)
    init_db(conn)
    try:
        yield conn
    finally:
        conn.close()
