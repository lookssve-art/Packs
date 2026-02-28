#!/usr/bin/env python3
"""Start the real-time pack data collector daemon.

Continuously polls Magic Eden for new pack rips, drop rate changes,
and computes live EV / probability updates.

Usage: python scripts/run_collector.py [--discover]
"""

import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Settings
from src.collector.scheduler import run_collector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def main():
    settings = Settings()
    run_discovery = "--discover" in sys.argv

    print("=" * 60)
    print("Magic Eden Packs — Real-Time Collector")
    print("=" * 60)
    print(f"  Poll interval: {settings.poll_interval_seconds}s")
    print(f"  Database: {settings.db_path}")
    print(f"  API Key: {'configured' if settings.me_api_key else 'not set'}")
    print(f"  Run discovery: {run_discovery}")
    print(f"  Half-life: {settings.default_half_life_hours}h")
    print(f"  Max pulls window: {settings.max_pulls_window}")
    print("=" * 60)
    print("Press Ctrl+C to stop.\n")

    asyncio.run(run_collector(settings, run_discovery=run_discovery))


if __name__ == "__main__":
    main()
