#!/usr/bin/env python3
"""CLI entry point for the eBay Arbitrage Scanner.

Usage:
    # Run a single scan now
    python -m src.run_ebay_arbitrage scan

    # Start the scheduler (runs at 8:00 and 20:00 CET)
    python -m src.run_ebay_arbitrage schedule

    # Get latest stored opportunities
    python -m src.run_ebay_arbitrage latest

Environment variables:
    EBAY_DISCORD_WEBHOOK  – Discord webhook URL for reports
    EBAY_ARBITRAGE_DB     – SQLite database path (default: ebay_arbitrage.db)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from ebay_arbitrage.config import ScannerConfig
from ebay_arbitrage.database import get_latest_opportunities, init_db
from ebay_arbitrage.scheduler import run_scan_cycle, run_scheduler


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cmd_scan(config: ScannerConfig) -> None:
    """Run a single scan cycle."""
    opportunities = asyncio.run(run_scan_cycle(config))
    print(f"\n{'='*60}")
    print(f"  Found {len(opportunities)} arbitrage opportunities")
    print(f"{'='*60}\n")
    for i, opp in enumerate(opportunities, 1):
        print(
            f"  #{i} {opp['keyword']}\n"
            f"     {opp['source_region'].upper()} €{opp['source_avg_price']:.2f}"
            f" → DE €{opp['de_avg_price']:.2f}"
            f" | Profit: €{opp['profit_eur']:.2f} ({opp['margin_pct']:.0f}%)\n"
        )


def cmd_latest(config: ScannerConfig) -> None:
    """Show latest stored opportunities."""
    init_db(config.db_path)
    opps = get_latest_opportunities(config.db_path, limit=config.top_n)
    if not opps:
        print("No opportunities stored yet. Run 'scan' first.")
        return

    print(f"\nLatest {len(opps)} opportunities:\n")
    for i, opp in enumerate(opps, 1):
        print(
            f"  #{i} {opp['keyword']}\n"
            f"     {opp['source_region'].upper()} €{opp['source_avg_price']:.2f}"
            f" → DE €{opp['de_avg_price']:.2f}"
            f" | Profit: €{opp['profit_eur']:.2f} ({opp['margin_pct']:.0f}%)\n"
        )


def cmd_schedule(config: ScannerConfig) -> None:
    """Start the scheduler daemon."""
    print("Starting eBay Arbitrage Scheduler (8:00 & 20:00 CET)")
    print("Press Ctrl+C to stop.\n")
    try:
        asyncio.run(run_scheduler(config))
    except KeyboardInterrupt:
        print("\nScheduler stopped.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="eBay Arbitrage Scanner – find deals across eBay regions"
    )
    parser.add_argument(
        "command",
        choices=["scan", "schedule", "latest"],
        help="scan: run once | schedule: run at 8/20 CET | latest: show stored results",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    parser.add_argument(
        "--webhook", type=str, default="", help="Discord webhook URL"
    )
    parser.add_argument(
        "--db", type=str, default="ebay_arbitrage.db", help="SQLite DB path"
    )
    parser.add_argument(
        "--top", type=int, default=10, help="Number of top results"
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    config = ScannerConfig(
        db_path=args.db,
        discord_webhook_url=args.webhook,
        top_n=args.top,
    )

    commands = {
        "scan": cmd_scan,
        "schedule": cmd_schedule,
        "latest": cmd_latest,
    }
    commands[args.command](config)


if __name__ == "__main__":
    main()
