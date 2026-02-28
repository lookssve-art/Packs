"""Playwright-based API endpoint discovery for Magic Eden Packs.

Navigates to magiceden.io/packs, intercepts all XHR/fetch requests,
and catalogs discovered API endpoints for later direct polling.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


async def discover_endpoints(
    output_path: str = "data/discovered_endpoints.json",
    headless: bool = True,
    timeout_ms: int = 30000,
) -> list[dict[str, Any]]:
    """Launch headless browser, intercept API calls on the Packs page.

    Discovers:
    - Drop rate endpoints
    - Recent pull/activity feed endpoints
    - Pack listing/detail endpoints

    Returns list of discovered endpoint descriptors.
    """
    from playwright.async_api import async_playwright

    discovered: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )
        # Block service workers to avoid caching issues
        await context.add_init_script(
            "delete navigator.serviceWorker;"
        )
        page = await context.new_page()

        async def on_response(response):
            url = response.url
            if url in seen_urls:
                return
            seen_urls.add(url)

            # Filter for API-like responses
            api_indicators = [
                "api-mainnet.magiceden",
                "magiceden.io/api",
                "magiceden.us/api",
                "_next/data",
                "/rpc/",
                "/v2/",
                "/v3/",
                "packs",
                "collector",
                "tokenized",
                "drop-rate",
                "droprate",
                "activity",
                "recent",
                "pulls",
                "rips",
            ]

            url_lower = url.lower()
            if not any(ind in url_lower for ind in api_indicators):
                return

            # Skip static assets
            if any(url_lower.endswith(ext) for ext in [
                ".js", ".css", ".png", ".jpg", ".svg", ".woff", ".woff2",
            ]):
                return

            content_type = response.headers.get("content-type", "")
            if "json" not in content_type and "text" not in content_type:
                return

            try:
                body = await response.text()
                # Try to parse as JSON
                try:
                    json_body = json.loads(body)
                    if isinstance(json_body, dict):
                        sample_keys = list(json_body.keys())[:20]
                    elif isinstance(json_body, list):
                        sample_keys = f"array[{len(json_body)}]"
                    else:
                        sample_keys = str(type(json_body))
                except (json.JSONDecodeError, ValueError):
                    sample_keys = "non-json"
                    json_body = None

                entry = {
                    "url": url,
                    "method": response.request.method,
                    "status": response.status,
                    "content_type": content_type,
                    "sample_keys": sample_keys,
                    "response_size": len(body),
                    "sample_response": body[:3000],
                    "category": _categorize_endpoint(url),
                }
                discovered.append(entry)
                logger.info(
                    "Discovered endpoint: %s [%s] %s",
                    response.request.method,
                    response.status,
                    url[:120],
                )
            except Exception as e:
                logger.debug("Could not read response for %s: %s", url[:80], e)

        page.on("response", on_response)

        # Step 1: Navigate to Packs page
        logger.info("Navigating to magiceden.io/packs...")
        try:
            await page.goto(
                "https://magiceden.io/packs",
                wait_until="networkidle",
                timeout=timeout_ms,
            )
        except Exception:
            # Try alternative URL
            try:
                await page.goto(
                    "https://magiceden.us/packs",
                    wait_until="networkidle",
                    timeout=timeout_ms,
                )
            except Exception as e:
                logger.error("Failed to navigate to packs page: %s", e)

        await page.wait_for_timeout(3000)

        # Step 2: Click through pack types to trigger API calls
        pack_selectors = [
            "text=Sapphire",
            "text=Emerald",
            "text=Ruby",
            "text=Diamond",
            "text=Pokémon",
            "text=Pokemon",
        ]
        for selector in pack_selectors:
            try:
                elem = page.locator(selector).first
                if await elem.is_visible(timeout=2000):
                    await elem.click()
                    await page.wait_for_timeout(2000)
            except Exception:
                pass

        # Step 3: Click "View Drop Rates" buttons
        drop_rate_selectors = [
            "text=View Drop Rates",
            "text=Drop Rates",
            "text=View Odds",
            "[data-testid*='drop-rate']",
            "[class*='dropRate']",
            "button:has-text('Rates')",
        ]
        for selector in drop_rate_selectors:
            try:
                elements = page.locator(selector)
                count = await elements.count()
                for i in range(min(count, 5)):
                    try:
                        await elements.nth(i).click()
                        await page.wait_for_timeout(2000)
                    except Exception:
                        pass
            except Exception:
                pass

        # Step 4: Scroll to trigger lazy-loaded content (activity feed)
        for _ in range(5):
            await page.evaluate("window.scrollBy(0, 800)")
            await page.wait_for_timeout(1500)

        # Step 5: Look for activity/recent pulls section
        activity_selectors = [
            "text=Recent",
            "text=Activity",
            "text=Recent Pulls",
            "text=Latest Rips",
        ]
        for selector in activity_selectors:
            try:
                elem = page.locator(selector).first
                if await elem.is_visible(timeout=2000):
                    await elem.click()
                    await page.wait_for_timeout(2000)
            except Exception:
                pass

        await browser.close()

    # Save discovered endpoints
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        # Don't save full response bodies to keep file manageable
        save_data = []
        for ep in discovered:
            save_ep = {k: v for k, v in ep.items() if k != "sample_response"}
            save_ep["sample_response_truncated"] = ep.get("sample_response", "")[:500]
            save_data.append(save_ep)
        json.dump(save_data, f, indent=2)

    logger.info("Discovered %d endpoints, saved to %s", len(discovered), output_path)
    return discovered


def load_discovered_endpoints(
    path: str = "data/discovered_endpoints.json",
) -> list[dict[str, Any]]:
    """Load previously discovered endpoints from cache."""
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def _categorize_endpoint(url: str) -> str:
    """Categorize an endpoint based on URL patterns."""
    url_lower = url.lower()
    if any(k in url_lower for k in ["drop-rate", "droprate", "odds", "rates"]):
        return "drop_rates"
    if any(k in url_lower for k in ["activity", "recent", "pulls", "rips", "history"]):
        return "activity_feed"
    if any(k in url_lower for k in ["pack", "product", "listing"]):
        return "pack_listing"
    if "_next/data" in url_lower:
        return "next_data"
    if "/v2/" in url_lower:
        return "me_v2_api"
    if "/rpc/" in url_lower:
        return "me_rpc"
    return "other"
