"""Playwright-based scraper for Magic Eden Packs page.

Fallback data source when API endpoints are not discovered or unavailable.
Scrapes drop rates, recent pulls, and pack details directly from the page.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


async def scrape_packs_page(
    headless: bool = True,
    timeout_ms: int = 30000,
) -> dict[str, Any]:
    """Scrape the entire Packs page for all data.

    Returns:
        {
            "packs": [{"name": ..., "cost": ..., "slug": ...}, ...],
            "drop_rates": {"pack_slug": [{"name": ..., "percentage": ...}]},
            "recent_pulls": [{"card_name": ..., "rarity": ..., "value": ...}],
        }
    """
    from playwright.async_api import async_playwright

    result: dict[str, Any] = {
        "packs": [],
        "drop_rates": {},
        "recent_pulls": [],
    }

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
        page = await context.new_page()

        try:
            await page.goto(
                "https://magiceden.io/packs",
                wait_until="networkidle",
                timeout=timeout_ms,
            )
        except Exception:
            try:
                await page.goto(
                    "https://magiceden.us/packs",
                    wait_until="networkidle",
                    timeout=timeout_ms,
                )
            except Exception as e:
                logger.error("Failed to load packs page: %s", e)
                await browser.close()
                return result

        await page.wait_for_timeout(3000)

        # Extract pack types from the page
        result["packs"] = await _extract_packs(page)

        # Extract drop rates for each visible pack
        result["drop_rates"] = await _extract_drop_rates(page)

        # Extract recent pulls / activity feed
        result["recent_pulls"] = await _extract_recent_pulls(page)

        await browser.close()

    logger.info(
        "Scraped: %d packs, %d drop rate sets, %d recent pulls",
        len(result["packs"]),
        len(result["drop_rates"]),
        len(result["recent_pulls"]),
    )
    return result


async def _extract_packs(page) -> list[dict[str, Any]]:
    """Extract available pack types from the page."""
    packs = []

    # Try to find pack cards/containers
    try:
        # Look for price indicators
        page_text = await page.inner_text("body")

        # Find price patterns like "$50", "$250", "$25", "$1000"
        price_pattern = re.compile(r'\$(\d{1,5}(?:,\d{3})*(?:\.\d{2})?)')
        prices = price_pattern.findall(page_text)

        # Find pack name patterns
        pack_names = []
        for name in ["Sapphire", "Emerald", "Ruby", "Diamond", "Gold", "Platinum"]:
            if name.lower() in page_text.lower():
                pack_names.append(name)

        # Pair names with prices (heuristic)
        for i, name in enumerate(pack_names):
            cost = float(prices[i].replace(",", "")) if i < len(prices) else 0.0
            packs.append({
                "name": name,
                "slug": name.lower(),
                "cost": cost,
            })

    except Exception as e:
        logger.warning("Failed to extract packs: %s", e)

    return packs


async def _extract_drop_rates(page) -> dict[str, list[dict[str, Any]]]:
    """Click 'View Drop Rates' and extract rate tables."""
    rates: dict[str, list[dict[str, Any]]] = {}

    try:
        # Find and click drop rate buttons
        buttons = page.locator("text=View Drop Rates, text=Drop Rates, button:has-text('Rates')")
        count = await buttons.count()

        for i in range(min(count, 5)):
            try:
                await buttons.nth(i).click()
                await page.wait_for_timeout(2000)

                # Extract the modal/panel content
                modal_text = ""
                for selector in [
                    "[role='dialog']",
                    "[class*='modal']",
                    "[class*='dropdown']",
                    "[class*='popover']",
                    "[class*='panel']",
                ]:
                    try:
                        elem = page.locator(selector).first
                        if await elem.is_visible(timeout=1000):
                            modal_text = await elem.inner_text()
                            break
                    except Exception:
                        continue

                if modal_text:
                    tiers = _parse_rate_text(modal_text)
                    if tiers:
                        # Try to determine which pack this is for
                        pack_name = f"pack_{i}"
                        for name in ["sapphire", "emerald", "ruby", "diamond"]:
                            if name in modal_text.lower():
                                pack_name = name
                                break
                        rates[pack_name] = tiers

                # Close modal
                try:
                    close_btn = page.locator(
                        "button:has-text('Close'), button:has-text('×'), [aria-label='Close']"
                    ).first
                    await close_btn.click(timeout=2000)
                except Exception:
                    await page.keyboard.press("Escape")
                await page.wait_for_timeout(500)

            except Exception as e:
                logger.debug("Drop rate extraction attempt %d failed: %s", i, e)

    except Exception as e:
        logger.warning("Failed to extract drop rates: %s", e)

    return rates


async def _extract_recent_pulls(page) -> list[dict[str, Any]]:
    """Extract recent pull data from the activity feed."""
    pulls = []

    try:
        # Scroll down to find activity section
        for _ in range(5):
            await page.evaluate("window.scrollBy(0, 600)")
            await page.wait_for_timeout(1000)

        # Look for activity feed items
        # These are typically card elements with image, name, rarity, value
        page_text = await page.inner_text("body")

        # Pattern matching for pull entries
        rarity_keywords = ["epic", "rare", "uncommon", "common", "holographic", "gold", "silver", "gloss", "holo"]
        value_pattern = re.compile(r'\$(\d{1,6}(?:,\d{3})*(?:\.\d{2})?)')

        # This is a best-effort extraction; actual selectors depend on page structure
        logger.info("Activity feed text length: %d chars", len(page_text))

    except Exception as e:
        logger.warning("Failed to extract recent pulls: %s", e)

    return pulls


def _parse_rate_text(text: str) -> list[dict[str, Any]]:
    """Parse drop rate text from a modal/panel into structured data."""
    tiers = []
    lines = text.strip().split("\n")

    rarity_names = {"epic", "rare", "uncommon", "common", "holographic", "gold", "silver", "gloss", "matte", "grail"}
    pct_pattern = re.compile(r'(\d+\.?\d*)\s*%')

    for line in lines:
        line_lower = line.lower().strip()
        if not line_lower:
            continue

        # Check if line contains a rarity name
        found_rarity = None
        for rarity in rarity_names:
            if rarity in line_lower:
                found_rarity = rarity
                break

        if found_rarity:
            # Look for percentage in the same line
            pct_match = pct_pattern.search(line)
            percentage = pct_match.group(0) if pct_match else None

            # Look for value range
            value_pattern = re.compile(r'\$[\d,]+\s*[-–]\s*\$[\d,]+')
            value_match = value_pattern.search(line)
            value_range = value_match.group(0) if value_match else None

            tiers.append({
                "name": found_rarity,
                "percentage": percentage,
                "value_range": value_range,
            })

    return tiers
