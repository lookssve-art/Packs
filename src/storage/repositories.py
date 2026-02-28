"""CRUD repositories for all database entities."""

from __future__ import annotations

import datetime
import json
import sqlite3
from typing import Optional

from src.models.dataclasses import (
    Alert,
    DropRateSnapshot,
    EVResult,
    PackTypeInfo,
    Pull,
)


class PullRepository:
    """Repository for pack pull records."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def insert(self, pull: Pull) -> bool:
        """Insert a pull, returns False if duplicate (pull_id already exists)."""
        try:
            self.conn.execute(
                """INSERT INTO pulls
                   (pull_id, timestamp, pack_type, card_name, card_id,
                    token_mint, rarity, value_bucket, estimated_value,
                    payout_value, image_url, source, snapshot_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    pull.pull_id,
                    pull.timestamp.isoformat(),
                    pull.pack_type,
                    pull.card_name,
                    pull.card_id,
                    pull.token_mint,
                    pull.rarity,
                    pull.value_bucket,
                    pull.estimated_value,
                    pull.payout_value,
                    pull.image_url,
                    pull.source,
                    pull.snapshot_id,
                ),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def insert_batch(self, pulls: list[Pull]) -> int:
        """Insert multiple pulls, skipping duplicates. Returns count of new inserts."""
        inserted = 0
        for pull in pulls:
            if self.insert(pull):
                inserted += 1
        return inserted

    def get_recent(
        self,
        pack_type: Optional[str] = None,
        limit: int = 4000,
        since: Optional[datetime.datetime] = None,
    ) -> list[Pull]:
        """Get recent pulls, optionally filtered by pack type and time."""
        query = "SELECT * FROM pulls"
        params: list = []
        conditions = []

        if pack_type:
            conditions.append("pack_type = ?")
            params.append(pack_type)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since.isoformat())

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_pull(r) for r in rows]

    def enrich(self, pull_id: str, card_name: str | None, image_url: str | None, rarity: str | None = None) -> bool:
        """Update an existing pull with enriched metadata. Returns True if a row was changed."""
        sets: list[str] = []
        params: list = []
        if card_name:
            sets.append("card_name = ?")
            params.append(card_name)
        if image_url:
            sets.append("image_url = ?")
            params.append(image_url)
        if rarity:
            sets.append("rarity = ?")
            params.append(rarity)
        if not sets:
            return False
        params.append(pull_id)
        cur = self.conn.execute(
            f"UPDATE pulls SET {', '.join(sets)} WHERE pull_id = ? AND (card_name IS NULL OR image_url IS NULL)",
            params,
        )
        self.conn.commit()
        return cur.rowcount > 0

    def get_unenriched(self, limit: int = 20) -> list[Pull]:
        """Get pulls that are missing card_name or image_url."""
        rows = self.conn.execute(
            """SELECT * FROM pulls
               WHERE (card_name IS NULL OR image_url IS NULL) AND token_mint IS NOT NULL
               ORDER BY timestamp DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [self._row_to_pull(r) for r in rows]

    def get_count_by_pack(self) -> dict[str, int]:
        """Get pull count per pack type."""
        rows = self.conn.execute(
            "SELECT pack_type, COUNT(*) as cnt FROM pulls GROUP BY pack_type"
        ).fetchall()
        return {r["pack_type"]: r["cnt"] for r in rows}

    def _row_to_pull(self, row: sqlite3.Row) -> Pull:
        return Pull(
            pull_id=row["pull_id"],
            timestamp=datetime.datetime.fromisoformat(row["timestamp"]),
            pack_type=row["pack_type"],
            rarity=row["rarity"],
            card_name=row["card_name"],
            card_id=row["card_id"],
            token_mint=row["token_mint"],
            value_bucket=row["value_bucket"],
            estimated_value=row["estimated_value"],
            payout_value=row["payout_value"],
            image_url=row["image_url"],
            source=row["source"],
            snapshot_id=row["snapshot_id"],
        )


class SnapshotRepository:
    """Repository for drop rate snapshots."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def insert(self, snapshot: DropRateSnapshot) -> int:
        """Insert a snapshot and return its ID."""
        cursor = self.conn.execute(
            """INSERT INTO drop_rate_snapshots (timestamp, pack_type, source, rates_json)
               VALUES (?, ?, ?, ?)""",
            (
                snapshot.timestamp.isoformat(),
                snapshot.pack_type,
                snapshot.source,
                json.dumps(snapshot.rates),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    def get_latest(self, pack_type: str) -> Optional[DropRateSnapshot]:
        """Get the most recent snapshot for a pack type."""
        row = self.conn.execute(
            """SELECT * FROM drop_rate_snapshots
               WHERE pack_type = ? ORDER BY timestamp DESC LIMIT 1""",
            (pack_type,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_snapshot(row)

    def get_history(
        self, pack_type: str, limit: int = 100
    ) -> list[DropRateSnapshot]:
        """Get snapshot history for a pack type."""
        rows = self.conn.execute(
            """SELECT * FROM drop_rate_snapshots
               WHERE pack_type = ? ORDER BY timestamp DESC LIMIT ?""",
            (pack_type, limit),
        ).fetchall()
        return [self._row_to_snapshot(r) for r in rows]

    def has_rates_changed(
        self, pack_type: str, new_rates: dict[str, float]
    ) -> bool:
        """Check if rates differ from the latest snapshot."""
        latest = self.get_latest(pack_type)
        if latest is None:
            return True
        return latest.rates != new_rates

    def _row_to_snapshot(self, row: sqlite3.Row) -> DropRateSnapshot:
        return DropRateSnapshot(
            id=row["id"],
            timestamp=datetime.datetime.fromisoformat(row["timestamp"]),
            pack_type=row["pack_type"],
            source=row["source"],
            rates=json.loads(row["rates_json"]),
        )


class EVSnapshotRepository:
    """Repository for computed EV snapshots."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def insert(self, ev: EVResult) -> int:
        cursor = self.conn.execute(
            """INSERT INTO ev_snapshots
               (timestamp, pack_type, model_mode, ev_value, ev_ratio,
                pack_cost, confidence_tier, obs_count, posterior_json,
                bucket_values_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.datetime.utcnow().isoformat(),
                ev.pack_type,
                ev.model_mode,
                ev.ev,
                ev.ev_ratio,
                ev.pack_cost,
                ev.confidence_tier,
                ev.obs_count,
                json.dumps(
                    {k: list(v) for k, v in ev.rarity_posteriors.items()}
                ),
                json.dumps(ev.calibrated_values),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    def get_history(
        self, pack_type: str, limit: int = 200
    ) -> list[dict]:
        """Get EV history for trend charts."""
        rows = self.conn.execute(
            """SELECT * FROM ev_snapshots
               WHERE pack_type = ? ORDER BY timestamp DESC LIMIT ?""",
            (pack_type, limit),
        ).fetchall()
        return [dict(r) for r in rows]


class AlertRepository:
    """Repository for alerts."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def insert(self, alert: Alert) -> int:
        cursor = self.conn.execute(
            """INSERT INTO alerts
               (timestamp, alert_type, pack_type, severity, message,
                details_json, acknowledged)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                alert.timestamp.isoformat(),
                alert.alert_type,
                alert.pack_type,
                alert.severity,
                alert.message,
                json.dumps(alert.details) if alert.details else None,
                int(alert.acknowledged),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    def get_active(self, limit: int = 50) -> list[Alert]:
        rows = self.conn.execute(
            """SELECT * FROM alerts WHERE acknowledged = 0
               ORDER BY timestamp DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [self._row_to_alert(r) for r in rows]

    def get_recent(self, limit: int = 100) -> list[Alert]:
        rows = self.conn.execute(
            "SELECT * FROM alerts ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_alert(r) for r in rows]

    def acknowledge(self, alert_id: int) -> None:
        self.conn.execute(
            "UPDATE alerts SET acknowledged = 1 WHERE id = ?", (alert_id,)
        )
        self.conn.commit()

    def _row_to_alert(self, row: sqlite3.Row) -> Alert:
        return Alert(
            id=row["id"],
            timestamp=datetime.datetime.fromisoformat(row["timestamp"]),
            alert_type=row["alert_type"],
            pack_type=row["pack_type"],
            severity=row["severity"],
            message=row["message"],
            details=json.loads(row["details_json"])
            if row["details_json"]
            else None,
            acknowledged=bool(row["acknowledged"]),
        )


class RawResponseRepository:
    """Repository for raw API/scraper responses."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def insert(
        self,
        source: str,
        response_body: str,
        endpoint: Optional[str] = None,
        request_params: Optional[str] = None,
        http_status: Optional[int] = None,
    ) -> int:
        cursor = self.conn.execute(
            """INSERT INTO raw_responses
               (timestamp, source, endpoint, request_params,
                response_body, http_status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                datetime.datetime.utcnow().isoformat(),
                source,
                endpoint,
                request_params,
                response_body,
                http_status,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]


class PackTypeRepository:
    """Repository for dynamically discovered pack types."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def upsert(self, pack: PackTypeInfo) -> None:
        """Insert or update a pack type."""
        now = datetime.datetime.utcnow().isoformat()
        self.conn.execute(
            """INSERT INTO pack_types
               (slug, display_name, cost_usd, sellback_rate,
                rarity_tiers, first_seen, last_seen, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(slug) DO UPDATE SET
                   display_name = excluded.display_name,
                   cost_usd = excluded.cost_usd,
                   sellback_rate = excluded.sellback_rate,
                   rarity_tiers = excluded.rarity_tiers,
                   last_seen = excluded.last_seen,
                   is_active = excluded.is_active""",
            (
                pack.slug,
                pack.display_name,
                pack.cost_usd,
                pack.sellback_rate,
                json.dumps(pack.rarity_tiers),
                now,
                now,
                int(pack.is_active),
            ),
        )
        self.conn.commit()

    def get_all_active(self) -> list[PackTypeInfo]:
        rows = self.conn.execute(
            "SELECT * FROM pack_types WHERE is_active = 1"
        ).fetchall()
        return [
            PackTypeInfo(
                slug=r["slug"],
                display_name=r["display_name"],
                cost_usd=r["cost_usd"],
                sellback_rate=r["sellback_rate"],
                rarity_tiers=json.loads(r["rarity_tiers"]),
                is_active=bool(r["is_active"]),
            )
            for r in rows
        ]

    def get_by_slug(self, slug: str) -> Optional[PackTypeInfo]:
        row = self.conn.execute(
            "SELECT * FROM pack_types WHERE slug = ?", (slug,)
        ).fetchone()
        if not row:
            return None
        return PackTypeInfo(
            slug=row["slug"],
            display_name=row["display_name"],
            cost_usd=row["cost_usd"],
            sellback_rate=row["sellback_rate"],
            rarity_tiers=json.loads(row["rarity_tiers"]),
            is_active=bool(row["is_active"]),
        )
