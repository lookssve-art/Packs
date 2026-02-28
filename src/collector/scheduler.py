"""Polling schedule manager for the collector daemon."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

from config.settings import Settings
from src.collector.orchestrator import Orchestrator

logger = logging.getLogger(__name__)


async def run_collector(
    settings: Settings | None = None,
    run_discovery: bool = False,
) -> None:
    """Start the collector daemon.

    Args:
        settings: Application settings (loads from env if None)
        run_discovery: Whether to run endpoint discovery on startup
    """
    settings = settings or Settings()
    orch = Orchestrator(settings)

    # Handle shutdown signals
    loop = asyncio.get_event_loop()
    shutdown_event = asyncio.Event()

    def _signal_handler():
        logger.info("Shutdown signal received")
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    try:
        await orch.initialize()

        if run_discovery:
            await orch.run_discovery()

        logger.info(
            "Collector started. Polling every %ds. Press Ctrl+C to stop.",
            settings.poll_interval_seconds,
        )

        while not shutdown_event.is_set():
            try:
                summary = await orch.run_cycle()
                if summary["errors"]:
                    logger.warning("Cycle errors: %s", summary["errors"])
            except Exception as e:
                logger.error("Cycle error: %s", e, exc_info=True)

            try:
                await asyncio.wait_for(
                    shutdown_event.wait(),
                    timeout=settings.poll_interval_seconds,
                )
            except asyncio.TimeoutError:
                pass  # Normal — timeout means it's time for next cycle

    finally:
        await orch.shutdown()
        logger.info("Collector stopped.")
