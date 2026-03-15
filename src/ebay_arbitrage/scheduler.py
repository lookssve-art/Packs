"""Scheduler – runs arbitrage scans at 8:00 and 20:00 CET."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from .analyzer import find_arbitrage, scan_de_trending
from .config import ScannerConfig
from .database import cleanup_old_data, init_db
from .discord_notifier import send_arbitrage_report

logger = logging.getLogger(__name__)

CET = timezone(timedelta(hours=1))


async def run_scan_cycle(config: ScannerConfig) -> list[dict]:
    """Execute a full scan cycle: scrape DE trending → compare → notify."""
    logger.info("=== Starting scan cycle ===")

    # 1. Scrape DE trending
    await scan_de_trending(config)

    # 2. Find arbitrage opportunities
    opportunities = await find_arbitrage(config)

    # 3. Send Discord report
    if opportunities:
        await send_arbitrage_report(
            config.discord_webhook_url,
            opportunities,
        )
    else:
        logger.info("No arbitrage opportunities found this cycle")

    # 4. Cleanup old data periodically
    cleanup_old_data(config.db_path, days=90)

    logger.info("=== Scan cycle complete: %d opportunities ===", len(opportunities))
    return opportunities


def _seconds_until_next_run(hours: list[int]) -> float:
    """Calculate seconds until the next scheduled run time (CET)."""
    now = datetime.now(CET)
    candidates = []
    for h in hours:
        target = now.replace(hour=h, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        candidates.append(target)

    next_run = min(candidates)
    delta = (next_run - now).total_seconds()
    logger.info(
        "Next run at %s CET (in %.0f minutes)",
        next_run.strftime("%H:%M"),
        delta / 60,
    )
    return delta


async def run_scheduler(config: ScannerConfig) -> None:
    """Run the scanner on schedule (default: 8:00 and 20:00 CET)."""
    init_db(config.db_path)
    logger.info("Scheduler started – runs at %s CET", config.schedule_hours)

    while True:
        wait = _seconds_until_next_run(config.schedule_hours)
        await asyncio.sleep(wait)

        try:
            await run_scan_cycle(config)
        except Exception:
            logger.exception("Scan cycle failed")

        # Small buffer to avoid running twice at the same minute
        await asyncio.sleep(61)
