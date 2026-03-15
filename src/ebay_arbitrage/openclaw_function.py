"""OpenClaw / Charizard Agent integration – exposes scanner as a callable function."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from .analyzer import find_arbitrage, scan_de_trending
from .config import ScannerConfig
from .database import get_de_trending, get_latest_opportunities, init_db

logger = logging.getLogger(__name__)


def get_function_definition() -> dict[str, Any]:
    """Return the OpenClaw function definition for the Charizard Agent."""
    return {
        "name": "ebay_arbitrage_scan",
        "description": (
            "Scans eBay Germany for trending sold items, compares prices with "
            "USA, Japan, and China eBay, and returns the top arbitrage opportunities "
            "where items can be bought cheaply abroad and sold for more in Germany."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["scan", "get_latest", "get_trending"],
                    "description": (
                        "scan: Run a full scan cycle. "
                        "get_latest: Return the most recent opportunities. "
                        "get_trending: Return current DE trending items."
                    ),
                },
                "top_n": {
                    "type": "integer",
                    "description": "Number of top results to return (default: 10)",
                    "default": 10,
                },
            },
            "required": ["action"],
        },
    }


async def handle_function_call(arguments: dict[str, Any]) -> str:
    """Handle an OpenClaw function call and return JSON result."""
    action = arguments.get("action", "get_latest")
    top_n = arguments.get("top_n", 10)

    config = ScannerConfig(top_n=top_n)
    init_db(config.db_path)

    if action == "scan":
        await scan_de_trending(config)
        opportunities = await find_arbitrage(config)
        return json.dumps(
            {
                "status": "ok",
                "opportunities_found": len(opportunities),
                "top_opportunities": opportunities[:top_n],
            },
            ensure_ascii=False,
        )

    elif action == "get_latest":
        opps = get_latest_opportunities(config.db_path, limit=top_n)
        return json.dumps(
            {"status": "ok", "opportunities": opps},
            ensure_ascii=False,
        )

    elif action == "get_trending":
        trending = get_de_trending(config.db_path, limit=top_n)
        return json.dumps(
            {"status": "ok", "trending_de": trending},
            ensure_ascii=False,
        )

    else:
        return json.dumps({"status": "error", "message": f"Unknown action: {action}"})


def run_function_sync(arguments: dict[str, Any]) -> str:
    """Synchronous wrapper for environments that don't support async."""
    return asyncio.run(handle_function_call(arguments))
