"""Resilient async HTTP client with retry and rate limiting."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.data_sources.rate_limiter import TokenBucketRateLimiter

logger = logging.getLogger(__name__)


class ResilientHTTPClient:
    """HTTP client with rate limiting, retry, and logging."""

    def __init__(
        self,
        rate_limiter: TokenBucketRateLimiter | None = None,
        api_key: str | None = None,
        timeout: float = 30.0,
    ):
        self.rate_limiter = rate_limiter or TokenBucketRateLimiter()
        headers = {"User-Agent": "PacksEVTracker/1.0"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self.client = httpx.AsyncClient(headers=headers, timeout=timeout)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(
            (httpx.HTTPStatusError, httpx.ConnectTimeout, httpx.ReadTimeout)
        ),
    )
    async def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any]:
        """GET request with rate limiting and retry."""
        await self.rate_limiter.acquire()
        logger.debug("GET %s params=%s", url, params)
        response = await self.client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(
            (httpx.HTTPStatusError, httpx.ConnectTimeout, httpx.ReadTimeout)
        ),
    )
    async def get_text(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> str:
        """GET request returning raw text."""
        await self.rate_limiter.acquire()
        response = await self.client.get(url, params=params)
        response.raise_for_status()
        return response.text

    async def close(self) -> None:
        await self.client.aclose()
