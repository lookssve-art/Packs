"""Token-bucket rate limiter for API requests."""

from __future__ import annotations

import asyncio
import time


class TokenBucketRateLimiter:
    """Async token-bucket rate limiter.

    Enforces both per-second (QPS) and per-minute (QPM) limits.
    """

    def __init__(
        self,
        rate: float = 2.0,
        burst: int = 5,
        per_minute_cap: int = 120,
    ):
        self.rate = rate
        self.burst = burst
        self.per_minute_cap = per_minute_cap
        self.tokens = float(burst)
        self.last_refill = time.monotonic()
        self.minute_counter = 0
        self.minute_start = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a token is available, then consume it."""
        async with self._lock:
            now = time.monotonic()

            # Refill tokens based on elapsed time
            elapsed = now - self.last_refill
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_refill = now

            # Check per-minute cap
            if now - self.minute_start >= 60:
                self.minute_counter = 0
                self.minute_start = now

            if self.minute_counter >= self.per_minute_cap:
                wait = 60 - (now - self.minute_start)
                if wait > 0:
                    await asyncio.sleep(wait)
                self.minute_counter = 0
                self.minute_start = time.monotonic()

            # Wait for token if bucket is empty
            if self.tokens < 1:
                wait = (1 - self.tokens) / self.rate
                await asyncio.sleep(wait)
                self.tokens = 0
            else:
                self.tokens -= 1

            self.minute_counter += 1
