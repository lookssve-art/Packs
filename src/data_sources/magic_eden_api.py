"""Magic Eden v2 REST API client for collection data."""

from __future__ import annotations

import logging
from typing import Any

from src.data_sources.http_client import ResilientHTTPClient

logger = logging.getLogger(__name__)


class MagicEdenAPIClient:
    """Client for Magic Eden's public v2 API."""

    DEFAULT_BASE_URL = "https://api-mainnet.magiceden.dev/v2"

    # Known Collector Crypt collection symbols
    COLLECTION_SYMBOLS = [
        "collector_crypt",
        "tokenized_collectibles_drop1",
        "tokenized_collectibles_drop2",
        "tokenized_collectibles_drop3",
        "tokenized_collectibles_drop4",
        "tokenized_collectibles_drop5",
        "tokenized_collectibles_drop6",
        "tokenized_collectibles_drop7",
        "tokenized_collectibles_drop8",
        "tokenized_collectibles_drop9",
    ]

    def __init__(
        self,
        http_client: ResilientHTTPClient,
        base_url: str | None = None,
    ):
        self.http = http_client
        self.base_url = base_url or self.DEFAULT_BASE_URL

    async def get_collection_activities(
        self,
        symbol: str,
        offset: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch collection activities (sales, listings, etc.)."""
        url = f"{self.base_url}/collections/{symbol}/activities"
        params = {"offset": offset, "limit": limit}
        try:
            result = await self.http.get(url, params)
            if isinstance(result, list):
                return result
            return []
        except Exception as e:
            logger.warning("Failed to fetch activities for %s: %s", symbol, e)
            return []

    async def get_collection_stats(self, symbol: str) -> dict[str, Any]:
        """Fetch collection statistics (floor price, volume, etc.)."""
        url = f"{self.base_url}/collections/{symbol}/stats"
        try:
            result = await self.http.get(url)
            return result if isinstance(result, dict) else {}
        except Exception as e:
            logger.warning("Failed to fetch stats for %s: %s", symbol, e)
            return {}

    async def get_token_metadata(self, mint_address: str) -> dict[str, Any]:
        """Fetch token metadata (name, image, attributes) for a given mint."""
        url = f"{self.base_url}/tokens/{mint_address}"
        try:
            result = await self.http.get(url)
            return result if isinstance(result, dict) else {}
        except Exception as e:
            logger.debug("Failed to fetch token metadata for %s: %s", mint_address, e)
            return {}

    async def enrich_pulls_metadata(
        self,
        pulls: list[dict[str, Any]],
        max_enrichments: int = 10,
    ) -> list[dict[str, Any]]:
        """Enrich pulls that are missing name/image with token metadata.

        Only enriches up to max_enrichments per call to respect rate limits.
        """
        enriched = 0
        for pull in pulls:
            if enriched >= max_enrichments:
                break
            mint = pull.get("tokenMint") or pull.get("token_mint")
            if not mint:
                continue
            if pull.get("name") and pull.get("image"):
                continue

            meta = await self.get_token_metadata(mint)
            if meta:
                if not pull.get("name"):
                    pull["name"] = meta.get("name")
                if not pull.get("image"):
                    pull["image"] = meta.get("image")
                # Extract rarity from attributes if available
                for attr in (meta.get("attributes") or []):
                    if isinstance(attr, dict):
                        trait = (attr.get("trait_type") or "").lower()
                        if trait in ("rarity", "tier"):
                            pull["_enriched_rarity"] = str(
                                attr.get("value", "")
                            ).lower()
                enriched += 1

        logger.info("Enriched %d pulls with token metadata", enriched)
        return pulls

    async def get_all_activities(
        self,
        symbols: list[str] | None = None,
        limit_per_symbol: int = 100,
    ) -> dict[str, list[dict[str, Any]]]:
        """Fetch activities from all monitored collection symbols."""
        symbols = symbols or self.COLLECTION_SYMBOLS
        results: dict[str, list[dict[str, Any]]] = {}
        for symbol in symbols:
            activities = await self.get_collection_activities(
                symbol, limit=limit_per_symbol
            )
            if activities:
                results[symbol] = activities
                logger.info(
                    "Fetched %d activities from %s", len(activities), symbol
                )
        return results
