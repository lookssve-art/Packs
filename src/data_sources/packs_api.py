"""Client for discovered Packs-specific API endpoints.

Loads endpoint patterns from discovered_endpoints.json and provides
structured access to pack data. Falls back gracefully if endpoints
are unavailable.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.data_sources.discovery import load_discovered_endpoints
from src.data_sources.http_client import ResilientHTTPClient

logger = logging.getLogger(__name__)


class EndpointNotDiscovered(Exception):
    """Raised when a required endpoint hasn't been discovered yet."""
    pass


class PacksAPIClient:
    """Client for undocumented/discovered Pack-specific API endpoints."""

    def __init__(
        self,
        http_client: ResilientHTTPClient,
        endpoints_path: str = "data/discovered_endpoints.json",
    ):
        self.http = http_client
        self.endpoints_path = endpoints_path
        self._endpoints: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """Load and index discovered endpoints by category."""
        raw = load_discovered_endpoints(self.endpoints_path)
        for ep in raw:
            cat = ep.get("category", "other")
            if cat not in self._endpoints:
                self._endpoints[cat] = ep
            # Prefer endpoints with successful responses
            elif ep.get("status", 0) == 200:
                self._endpoints[cat] = ep

    def is_available(self, category: str) -> bool:
        """Check if a particular endpoint category has been discovered."""
        return category in self._endpoints

    async def get_recent_pulls(self, limit: int = 50) -> list[dict[str, Any]]:
        """Fetch recent pack rip results from discovered endpoint."""
        ep = self._endpoints.get("activity_feed")
        if not ep:
            raise EndpointNotDiscovered(
                "activity_feed: Run discover_endpoints.py first"
            )

        url = ep["url"]
        logger.info("Fetching recent pulls from %s", url[:100])

        try:
            result = await self.http.get(url)
            if isinstance(result, list):
                return result[:limit]
            elif isinstance(result, dict):
                # Try common response wrapper keys
                for key in ["data", "items", "results", "pulls", "activities"]:
                    if key in result and isinstance(result[key], list):
                        return result[key][:limit]
            return []
        except Exception as e:
            logger.warning("Failed to fetch recent pulls: %s", e)
            return []

    async def get_drop_rates(self, pack_type: str = "") -> dict[str, Any]:
        """Fetch current drop rate table from discovered endpoint."""
        ep = self._endpoints.get("drop_rates")
        if not ep:
            raise EndpointNotDiscovered(
                "drop_rates: Run discover_endpoints.py first"
            )

        url = ep["url"]
        logger.info("Fetching drop rates from %s", url[:100])

        try:
            result = await self.http.get(url)
            return result if isinstance(result, dict) else {}
        except Exception as e:
            logger.warning("Failed to fetch drop rates: %s", e)
            return {}

    async def get_pack_listings(self) -> list[dict[str, Any]]:
        """Fetch available pack types and their details."""
        ep = self._endpoints.get("pack_listing") or self._endpoints.get("next_data")
        if not ep:
            raise EndpointNotDiscovered(
                "pack_listing: Run discover_endpoints.py first"
            )

        url = ep["url"]
        try:
            result = await self.http.get(url)
            if isinstance(result, list):
                return result
            elif isinstance(result, dict):
                for key in ["data", "packs", "items", "products", "pageProps"]:
                    if key in result:
                        val = result[key]
                        if isinstance(val, list):
                            return val
                        elif isinstance(val, dict) and "packs" in val:
                            return val["packs"] if isinstance(val["packs"], list) else [val["packs"]]
            return []
        except Exception as e:
            logger.warning("Failed to fetch pack listings: %s", e)
            return []

    def get_all_endpoint_urls(self) -> dict[str, str]:
        """Return all discovered endpoint URLs grouped by category."""
        return {cat: ep["url"] for cat, ep in self._endpoints.items()}
