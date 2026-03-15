"""SQLite storage for eBay Arbitrage Scanner."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Generator


def init_db(db_path: str) -> None:
    """Create tables if they don't exist."""
    with _connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sold_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                region TEXT NOT NULL,
                title TEXT NOT NULL,
                price REAL NOT NULL,
                currency TEXT NOT NULL,
                price_eur REAL NOT NULL,
                category TEXT,
                sold_date TEXT,
                url TEXT,
                scraped_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS trending_keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                region TEXT NOT NULL,
                keyword TEXT NOT NULL,
                sale_count INTEGER NOT NULL,
                avg_price_eur REAL NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(region, keyword)
            );

            CREATE TABLE IF NOT EXISTS arbitrage_opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                de_avg_price REAL NOT NULL,
                source_region TEXT NOT NULL,
                source_avg_price REAL NOT NULL,
                profit_eur REAL NOT NULL,
                margin_pct REAL NOT NULL,
                de_sale_count INTEGER NOT NULL,
                source_sale_count INTEGER NOT NULL,
                found_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_sold_region ON sold_items(region);
            CREATE INDEX IF NOT EXISTS idx_sold_scraped ON sold_items(scraped_at);
            CREATE INDEX IF NOT EXISTS idx_trending_region ON trending_keywords(region);
            CREATE INDEX IF NOT EXISTS idx_arb_found ON arbitrage_opportunities(found_at);
            """
        )


@contextmanager
def _connect(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def insert_sold_items(
    db_path: str,
    items: list[dict],
) -> int:
    """Insert sold items, return count inserted."""
    with _connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO sold_items (region, title, price, currency, price_eur, category, sold_date, url)
            VALUES (:region, :title, :price, :currency, :price_eur, :category, :sold_date, :url)
            """,
            items,
        )
        return len(items)


def upsert_trending(db_path: str, region: str, keyword: str, sale_count: int, avg_price_eur: float) -> None:
    """Insert or update a trending keyword."""
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO trending_keywords (region, keyword, sale_count, avg_price_eur, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(region, keyword) DO UPDATE SET
                sale_count = excluded.sale_count,
                avg_price_eur = excluded.avg_price_eur,
                updated_at = excluded.updated_at
            """,
            (region, keyword, sale_count, avg_price_eur),
        )


def get_de_trending(db_path: str, limit: int = 50) -> list[dict]:
    """Get top trending keywords from eBay.de by sale count."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT keyword, sale_count, avg_price_eur
            FROM trending_keywords
            WHERE region = 'de'
            ORDER BY sale_count DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def insert_opportunities(db_path: str, opps: list[dict]) -> None:
    """Store arbitrage opportunities."""
    with _connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO arbitrage_opportunities
                (keyword, de_avg_price, source_region, source_avg_price,
                 profit_eur, margin_pct, de_sale_count, source_sale_count)
            VALUES
                (:keyword, :de_avg_price, :source_region, :source_avg_price,
                 :profit_eur, :margin_pct, :de_sale_count, :source_sale_count)
            """,
            opps,
        )


def get_latest_opportunities(db_path: str, limit: int = 10) -> list[dict]:
    """Get the most recent top opportunities."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM arbitrage_opportunities
            ORDER BY found_at DESC, margin_pct DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def cleanup_old_data(db_path: str, days: int = 90) -> None:
    """Remove sold items older than N days."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM sold_items WHERE scraped_at < ?", (cutoff,))
