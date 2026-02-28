"""Tests for FastAPI API routes."""

import datetime
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from config.settings import Settings
from src.api.main import app
from src.api.websocket_manager import WebSocketManager
from src.models.dataclasses import PackTypeInfo, Pull
from src.storage.database import init_db
from src.storage.repositories import (
    AlertRepository,
    EVSnapshotRepository,
    PackTypeRepository,
    PullRepository,
    SnapshotRepository,
)


@pytest.fixture
def test_app():
    """Create a test app with in-memory database."""
    # Use check_same_thread=False because FastAPI TestClient runs
    # route handlers in a separate worker thread.
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)

    # Set up app state
    app.state.settings = Settings(db_path=":memory:")
    app.state.conn = conn
    app.state.ws_manager = WebSocketManager()

    # Seed some data
    pack_repo = PackTypeRepository(conn)
    pack_repo.upsert(PackTypeInfo(
        slug="sapphire", display_name="Sapphire",
        cost_usd=50.0, sellback_rate=0.85,
    ))
    pack_repo.upsert(PackTypeInfo(
        slug="emerald", display_name="Emerald",
        cost_usd=250.0, sellback_rate=0.90,
    ))

    pull_repo = PullRepository(conn)
    now = datetime.datetime.utcnow()
    for i in range(10):
        pull_repo.insert(Pull(
            pull_id=f"test_pull_{i}",
            timestamp=now - datetime.timedelta(minutes=i),
            pack_type="sapphire",
            rarity=["gloss", "gloss", "silver", "gloss", "gold",
                     "gloss", "silver", "gloss", "gloss", "holographic"][i],
            card_name=f"Card {i}",
            estimated_value=50.0 + i * 10,
            source="test",
        ))

    yield TestClient(app)
    conn.close()


class TestStatusRoute:
    def test_get_status(self, test_app):
        resp = test_app.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_pulls" in data
        assert data["total_pulls"] == 10
        assert "pack_types" in data

    def test_status_includes_pack_types(self, test_app):
        resp = test_app.get("/api/status")
        data = resp.json()
        assert "sapphire" in data["pack_types"]
        assert "emerald" in data["pack_types"]


class TestPacksRoute:
    def test_get_packs(self, test_app):
        resp = test_app.get("/api/packs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        slugs = {p["slug"] for p in data}
        assert "sapphire" in slugs
        assert "emerald" in slugs

    def test_pack_has_buy_url(self, test_app):
        resp = test_app.get("/api/packs")
        data = resp.json()
        for p in data:
            assert "buy_url" in p
            assert "magiceden" in p["buy_url"]


class TestEVRoute:
    def test_get_all_ev(self, test_app):
        resp = test_app.get("/api/ev/all")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        ev = data[0]
        assert "ev" in ev
        assert "ev_ratio" in ev
        assert "confidence_tier" in ev
        assert "rarity_posteriors" in ev
        assert "calibrated_values" in ev

    def test_ev_with_half_life(self, test_app):
        resp = test_app.get("/api/ev/all?half_life=12")
        assert resp.status_code == 200

    def test_ev_history_empty(self, test_app):
        resp = test_app.get("/api/ev/sapphire/history")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestPullsRoute:
    def test_get_recent(self, test_app):
        resp = test_app.get("/api/pulls/recent")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 10
        assert data[0]["pack_type"] == "sapphire"

    def test_filter_by_pack(self, test_app):
        resp = test_app.get("/api/pulls/recent?pack_type=emerald")
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_limit(self, test_app):
        resp = test_app.get("/api/pulls/recent?limit=3")
        assert resp.status_code == 200
        assert len(resp.json()) == 3


class TestRankingsRoute:
    def test_get_rankings(self, test_app):
        resp = test_app.get("/api/rankings")
        assert resp.status_code == 200
        data = resp.json()
        assert "rare_plus" in data
        assert "super_rare" in data
        assert "ev_ratio" in data
        assert "conservative" in data
        for mode in data.values():
            assert isinstance(mode, list)


class TestSnapshotsRoute:
    def test_get_empty_snapshots(self, test_app):
        resp = test_app.get("/api/snapshots/sapphire")
        assert resp.status_code == 200
        assert resp.json() == []


class TestAlertsRoute:
    def test_get_active_alerts(self, test_app):
        resp = test_app.get("/api/alerts/active")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_alert_history(self, test_app):
        resp = test_app.get("/api/alerts/history")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestIndexRoute:
    def test_index_serves_html(self, test_app):
        resp = test_app.get("/")
        assert resp.status_code == 200
        # Either HTML file or fallback JSON
        content_type = resp.headers.get("content-type", "")
        assert "html" in content_type or "json" in content_type
