"""Main collection orchestrator — polls data sources and updates database.

Runs as a persistent background daemon, polling every N seconds.
Each cycle: fetch data → parse → deduplicate → store → check alerts.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import sqlite3
from typing import Any

from config.constants import KNOWN_PACKS, PUBLISHED_DROP_RATES
from config.settings import Settings
from src.alerts.detector import AlertDetector
from src.data_sources.discovery import discover_endpoints
from src.data_sources.http_client import ResilientHTTPClient
from src.data_sources.magic_eden_api import MagicEdenAPIClient
from src.data_sources.packs_api import EndpointNotDiscovered, PacksAPIClient
from src.data_sources.rate_limiter import TokenBucketRateLimiter
from src.models.dataclasses import PackTypeInfo
from src.models.ev_calculator import compute_all_evs
from src.parsers.activity_parser import parse_collection_activities
from src.parsers.drop_rate_parser import (
    parse_drop_rates_from_api,
    parse_drop_rates_from_scrape,
)
from src.parsers.pull_parser import parse_packs_api_pull, set_sol_price
from src.storage.database import get_connection, init_db
from src.storage.repositories import (
    AlertRepository,
    EVSnapshotRepository,
    PackTypeRepository,
    PullRepository,
    RawResponseRepository,
    SnapshotRepository,
)

logger = logging.getLogger(__name__)


class Orchestrator:
    """Central collection loop that coordinates all data sources."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.conn: sqlite3.Connection | None = None
        self.http: ResilientHTTPClient | None = None
        self.me_api: MagicEdenAPIClient | None = None
        self.packs_api: PacksAPIClient | None = None
        self.cycle_count = 0

    async def initialize(self) -> None:
        """Set up database, HTTP client, and API clients."""
        # Database
        self.conn = get_connection(self.settings.db_path)
        init_db(self.conn)

        # Repositories
        self.pull_repo = PullRepository(self.conn)
        self.snapshot_repo = SnapshotRepository(self.conn)
        self.ev_repo = EVSnapshotRepository(self.conn)
        self.alert_repo = AlertRepository(self.conn)
        self.raw_repo = RawResponseRepository(self.conn)
        self.pack_type_repo = PackTypeRepository(self.conn)

        # HTTP client with rate limiting
        rate_limiter = TokenBucketRateLimiter(
            rate=self.settings.me_rate_limit_qps,
            burst=self.settings.me_rate_limit_burst,
            per_minute_cap=self.settings.me_rate_limit_qpm,
        )
        self.http = ResilientHTTPClient(
            rate_limiter=rate_limiter,
            api_key=self.settings.me_api_key,
        )

        # API clients
        self.me_api = MagicEdenAPIClient(
            http_client=self.http,
            base_url=self.settings.me_base_url,
        )
        self.packs_api = PacksAPIClient(
            http_client=self.http,
            endpoints_path=self.settings.discovery_cache_path,
        )

        # Alert detector
        self.alert_detector = AlertDetector(self.settings)

        # Register known pack types with correct display names
        display_names = {"ruby": "Ruby", "sapphire": "Sapphire", "emerald": "Emerald"}
        for slug, info in KNOWN_PACKS.items():
            self.pack_type_repo.upsert(PackTypeInfo(
                slug=slug,
                display_name=display_names.get(slug, slug.title()),
                cost_usd=info["cost"],
                sellback_rate=info.get("sellback_rate"),
            ))

        # Seed published drop rates so EV calculation works from the start
        for slug, rates in PUBLISHED_DROP_RATES.items():
            if not self.snapshot_repo.get_latest(slug):
                from src.models.dataclasses import DropRateSnapshot
                snapshot = DropRateSnapshot(
                    timestamp=datetime.datetime.utcnow(),
                    pack_type=slug,
                    rates=rates,
                    source="published_collector_crypt",
                )
                self.snapshot_repo.insert(snapshot)
                logger.info("Seeded published drop rates for %s", slug)

        # Try to fetch current SOL price
        await self._update_sol_price()

        logger.info("Orchestrator initialized. DB: %s", self.settings.db_path)

    async def run_discovery(self) -> None:
        """Run API endpoint discovery (should be done at startup or periodically)."""
        logger.info("Starting API endpoint discovery...")
        try:
            endpoints = await discover_endpoints(
                output_path=self.settings.discovery_cache_path,
                headless=self.settings.playwright_headless,
                timeout_ms=self.settings.playwright_timeout_ms,
            )
            logger.info("Discovered %d endpoints", len(endpoints))
            # Reload packs API with new endpoints
            self.packs_api = PacksAPIClient(
                http_client=self.http,
                endpoints_path=self.settings.discovery_cache_path,
            )
        except Exception as e:
            logger.error("Discovery failed: %s", e)

    async def run_cycle(self) -> dict[str, Any]:
        """Execute one collection cycle.

        Returns summary of what was collected.
        """
        self.cycle_count += 1
        cycle_start = datetime.datetime.utcnow()
        summary: dict[str, Any] = {
            "cycle": self.cycle_count,
            "timestamp": cycle_start.isoformat(),
            "new_pulls": 0,
            "new_snapshots": 0,
            "alerts_triggered": 0,
            "errors": [],
        }

        # 0. Update SOL price every 10 cycles (~7.5 min)
        if self.cycle_count % 10 == 1:
            await self._update_sol_price()

        # 1. Fetch from Packs API (discovered endpoints)
        try:
            packs_pulls = await self._fetch_packs_api()
            summary["new_pulls"] += packs_pulls
        except EndpointNotDiscovered as e:
            logger.debug("Packs API not available: %s", e)
        except Exception as e:
            summary["errors"].append(f"packs_api: {e}")
            logger.warning("Packs API error: %s", e)

        # 2. Fetch from ME Collection Activities API
        try:
            me_pulls = await self._fetch_me_activities()
            summary["new_pulls"] += me_pulls
        except Exception as e:
            summary["errors"].append(f"me_api: {e}")
            logger.warning("ME API error: %s", e)

        # 2b. Enrich existing pulls missing card_name/image
        try:
            enriched = await self._enrich_existing_pulls()
            if enriched:
                logger.info("Enriched %d existing pulls", enriched)
        except Exception as e:
            summary["errors"].append(f"enrich: {e}")
            logger.warning("Enrichment error: %s", e)

        # 3. Fetch drop rates
        try:
            new_snapshots = await self._fetch_drop_rates()
            summary["new_snapshots"] = new_snapshots
        except Exception as e:
            summary["errors"].append(f"drop_rates: {e}")
            logger.warning("Drop rates error: %s", e)

        # 4. Compute EV and check alerts
        try:
            alerts = await self._compute_ev_and_alerts()
            summary["alerts_triggered"] = alerts
        except Exception as e:
            summary["errors"].append(f"ev_compute: {e}")
            logger.warning("EV computation error: %s", e)

        elapsed = (datetime.datetime.utcnow() - cycle_start).total_seconds()
        logger.info(
            "Cycle %d complete in %.1fs: %d new pulls, %d snapshots, %d alerts",
            self.cycle_count,
            elapsed,
            summary["new_pulls"],
            summary["new_snapshots"],
            summary["alerts_triggered"],
        )
        return summary

    async def _fetch_packs_api(self) -> int:
        """Fetch pulls from discovered Packs API endpoints."""
        raw_pulls = await self.packs_api.get_recent_pulls(limit=100)
        if not raw_pulls:
            return 0

        # Store raw response
        self.raw_repo.insert(
            source="packs_api",
            response_body=json.dumps(raw_pulls)[:50000],
            endpoint="recent_pulls",
        )

        # Parse and store
        pulls = []
        for raw in raw_pulls:
            pull = parse_packs_api_pull(raw)
            if pull:
                pulls.append(pull)

        return self.pull_repo.insert_batch(pulls)

    async def _fetch_me_activities(self) -> int:
        """Fetch activities from ME v2 collection API."""
        all_activities = await self.me_api.get_all_activities(
            symbols=self.settings.collection_symbols,
            limit_per_symbol=100,
        )

        total_new = 0
        for symbol, activities in all_activities.items():
            # Enrich activities missing name/image with token metadata
            await self.me_api.enrich_pulls_metadata(
                activities, max_enrichments=10
            )

            # Store raw
            self.raw_repo.insert(
                source="api_v2_activities",
                response_body=json.dumps(activities)[:50000],
                endpoint=f"/v2/collections/{symbol}/activities",
            )

            # Parse
            pulls = parse_collection_activities(activities, pack_type=symbol)
            new_count = self.pull_repo.insert_batch(pulls)
            total_new += new_count

        return total_new

    async def _enrich_existing_pulls(self) -> int:
        """Fetch token metadata for pulls missing card_name/image and update DB."""
        from src.parsers.pull_parser import _normalize_rarity

        unenriched = self.pull_repo.get_unenriched(limit=10)
        if not unenriched:
            return 0

        count = 0
        for pull in unenriched:
            if not pull.token_mint:
                continue
            meta = await self.me_api.get_token_metadata(pull.token_mint)
            if not meta:
                continue

            card_name = meta.get("name")
            image_url = meta.get("image")
            rarity = None
            for attr in (meta.get("attributes") or []):
                if isinstance(attr, dict):
                    trait = (attr.get("trait_type") or "").lower()
                    if trait in ("rarity", "tier"):
                        raw = str(attr.get("value", "")).lower()
                        rarity = _normalize_rarity(raw)

            if self.pull_repo.enrich(pull.pull_id, card_name, image_url, rarity):
                count += 1
        return count

    async def _update_sol_price(self) -> None:
        """Fetch current SOL/USD price from CoinGecko (free, no key needed)."""
        try:
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {"ids": "solana", "vs_currencies": "usd"}
            result = await self.http.get(url, params)
            if isinstance(result, dict):
                price = result.get("solana", {}).get("usd")
                if price and float(price) > 0:
                    set_sol_price(float(price))
                    logger.info("SOL price updated: $%.2f", float(price))
        except Exception as e:
            logger.debug("Could not fetch SOL price: %s", e)

    async def _fetch_drop_rates(self) -> int:
        """Fetch and store drop rate snapshots."""
        new_snapshots = 0

        # Try Packs API first
        try:
            rates_data = await self.packs_api.get_drop_rates()
            if rates_data:
                for pack_type in self._get_active_pack_slugs():
                    snapshot = parse_drop_rates_from_api(rates_data, pack_type)
                    if snapshot and self.snapshot_repo.has_rates_changed(
                        pack_type, snapshot.rates
                    ):
                        self.snapshot_repo.insert(snapshot)
                        new_snapshots += 1
                        logger.info("Odds shift detected for %s!", pack_type)
        except EndpointNotDiscovered:
            pass

        return new_snapshots

    async def _compute_ev_and_alerts(self) -> int:
        """Compute EV for all packs and check alert conditions."""
        pack_types = self.pack_type_repo.get_all_active()
        if not pack_types:
            return 0

        # Get recent pulls
        all_pulls = self.pull_repo.get_recent(
            limit=self.settings.max_pulls_window
        )

        # Get published rates — start with hardcoded, override with DB snapshots
        published_rates: dict[str, dict[str, float]] = dict(PUBLISHED_DROP_RATES)
        for pack in pack_types:
            snapshot = self.snapshot_repo.get_latest(pack.slug)
            if snapshot:
                published_rates[pack.slug] = snapshot.rates

        # Compute EVs
        ev_results = compute_all_evs(
            all_pulls=all_pulls,
            pack_types=pack_types,
            published_rates=published_rates,
            half_life_hours=self.settings.default_half_life_hours,
            prior_strength=self.settings.prior_strength,
        )

        # Store EV snapshots
        for ev in ev_results:
            self.ev_repo.insert(ev)

        # Check alerts
        alerts = self.alert_detector.check_all(ev_results, published_rates)
        for alert in alerts:
            self.alert_repo.insert(alert)

        return len(alerts)

    def _get_active_pack_slugs(self) -> list[str]:
        """Get list of active pack type slugs."""
        packs = self.pack_type_repo.get_all_active()
        return [p.slug for p in packs] if packs else list(KNOWN_PACKS.keys())

    async def run_forever(self) -> None:
        """Main loop — run cycles at configured interval."""
        logger.info(
            "Starting continuous collection (interval: %ds)...",
            self.settings.poll_interval_seconds,
        )
        while True:
            try:
                await self.run_cycle()
            except Exception as e:
                logger.error("Cycle failed: %s", e, exc_info=True)

            await asyncio.sleep(self.settings.poll_interval_seconds)

    async def shutdown(self) -> None:
        """Clean up resources."""
        if self.http:
            await self.http.close()
        if self.conn:
            self.conn.close()
        logger.info("Orchestrator shut down.")
