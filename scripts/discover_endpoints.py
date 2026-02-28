#!/usr/bin/env python3
"""One-shot script to discover Magic Eden Packs API endpoints.

Run this before starting the collector to identify available
API endpoints for the Packs page.

Usage: python scripts/discover_endpoints.py
"""

import asyncio
import json
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Settings
from src.data_sources.discovery import discover_endpoints

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def main():
    settings = Settings()
    print("=" * 60)
    print("Magic Eden Packs — API Endpoint Discovery")
    print("=" * 60)
    print(f"Output: {settings.discovery_cache_path}")
    print(f"Headless: {settings.playwright_headless}")
    print()

    endpoints = await discover_endpoints(
        output_path=settings.discovery_cache_path,
        headless=settings.playwright_headless,
        timeout_ms=settings.playwright_timeout_ms,
    )

    print(f"\nDiscovered {len(endpoints)} endpoints:\n")

    # Group by category
    by_category: dict[str, list] = {}
    for ep in endpoints:
        cat = ep.get("category", "other")
        by_category.setdefault(cat, []).append(ep)

    for cat, eps in sorted(by_category.items()):
        print(f"  [{cat}] ({len(eps)} endpoints)")
        for ep in eps:
            print(f"    {ep['method']} [{ep['status']}] {ep['url'][:100]}")

    print(f"\nFull results saved to: {settings.discovery_cache_path}")


if __name__ == "__main__":
    asyncio.run(main())
