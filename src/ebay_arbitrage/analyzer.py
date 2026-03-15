"""Arbitrage analysis engine – compares DE prices with foreign sources."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from .config import REGIONS, ScannerConfig
from .database import (
    get_de_trending,
    insert_opportunities,
    insert_sold_items,
    upsert_trending,
)
from .scraper import SoldItem, fetch_exchange_rates, scrape_sold_listings

logger = logging.getLogger(__name__)

# Popular search terms to seed the scanner with trending items
SEED_QUERIES_DE = [
    "pokemon karten", "iphone", "samsung galaxy", "nintendo switch",
    "playstation 5", "lego", "airpods", "dyson", "nike jordan",
    "rolex", "gpu grafikkarte", "magic the gathering", "yu-gi-oh",
    "manga", "anime figur", "thermomix", "sony kamera", "macbook",
    "kindle", "gopro", "bose kopfhörer", "swatch", "funko pop",
    "vintage uhr", "retro konsole", "steiff", "montblanc",
    "leica", "playmobil", "ravensburger puzzle",
]

SOURCE_REGIONS = ["us", "jp", "cn"]


async def scan_de_trending(config: ScannerConfig) -> list[dict]:
    """Scan eBay.de for trending sold items and store results."""
    region = REGIONS["de"]
    all_items: list[dict] = []

    for query in SEED_QUERIES_DE:
        items = await scrape_sold_listings(region, query, config, max_pages=2)
        if not items:
            continue

        db_items = [_sold_item_to_dict(item, "de") for item in items]
        insert_sold_items(config.db_path, db_items)

        avg_price = sum(i.price_eur for i in items) / len(items)
        upsert_trending(config.db_path, "de", query, len(items), avg_price)

        all_items.extend(db_items)
        logger.info("DE trending: '%s' → %d sales, avg €%.2f", query, len(items), avg_price)

    return all_items


async def find_arbitrage(config: ScannerConfig) -> list[dict]:
    """Compare DE trending items with foreign eBay prices to find arbitrage."""
    rates = await fetch_exchange_rates()

    trending = get_de_trending(config.db_path, limit=30)
    if not trending:
        logger.warning("No DE trending data – run scan_de_trending first")
        return []

    opportunities: list[dict] = []

    for trend in trending:
        keyword = trend["keyword"]
        de_avg = trend["avg_price_eur"]
        de_count = trend["sale_count"]

        for region_key in SOURCE_REGIONS:
            region = REGIONS[region_key]
            items = await scrape_sold_listings(region, keyword, config, max_pages=1)
            if len(items) < 3:
                continue

            # Convert to EUR using live rates
            for item in items:
                rate = rates.get(item.currency, 1.0)
                item.price_eur = round(item.price * rate, 2)

            source_avg = sum(i.price_eur for i in items) / len(items)
            profit = de_avg - source_avg
            margin = (profit / source_avg * 100) if source_avg > 0 else 0

            if profit >= config.min_profit_eur and margin >= config.min_margin_pct:
                opp = {
                    "keyword": keyword,
                    "de_avg_price": round(de_avg, 2),
                    "source_region": region_key,
                    "source_avg_price": round(source_avg, 2),
                    "profit_eur": round(profit, 2),
                    "margin_pct": round(margin, 1),
                    "de_sale_count": de_count,
                    "source_sale_count": len(items),
                }
                opportunities.append(opp)
                logger.info(
                    "ARBITRAGE: '%s' DE €%.2f vs %s €%.2f → profit €%.2f (%.1f%%)",
                    keyword, de_avg, region_key.upper(), source_avg, profit, margin,
                )

            # Store foreign sold data too
            db_items = [_sold_item_to_dict(item, region_key) for item in items]
            insert_sold_items(config.db_path, db_items)

    # Sort by margin descending, take top N
    opportunities.sort(key=lambda x: x["margin_pct"], reverse=True)
    top = opportunities[: config.top_n]

    if top:
        insert_opportunities(config.db_path, top)

    return top


def _sold_item_to_dict(item: SoldItem, region: str) -> dict:
    return {
        "region": region,
        "title": item.title,
        "price": item.price,
        "currency": item.currency,
        "price_eur": item.price_eur,
        "category": item.category,
        "sold_date": item.sold_date,
        "url": item.url,
    }
