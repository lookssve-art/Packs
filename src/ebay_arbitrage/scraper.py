"""eBay sold-listings scraper using httpx + HTML parsing."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime

import httpx

from .config import DEFAULT_EXCHANGE_RATES, EbayRegion, ScannerConfig

logger = logging.getLogger(__name__)

# Regex patterns for parsing eBay sold listings HTML
_PRICE_RE = re.compile(r"[\d.,]+")
_ITEM_BLOCK_RE = re.compile(
    r'<div[^>]*class="[^"]*s-item__wrapper[^"]*"[^>]*>(.*?)</div>\s*</li>',
    re.DOTALL,
)
_TITLE_RE = re.compile(
    r'<(?:span|div)[^>]*class="[^"]*s-item__title[^"]*"[^>]*>'
    r"(?:<span[^>]*>)?(.*?)(?:</span>)?</(?:span|div)>",
    re.DOTALL,
)
_PRICE_TAG_RE = re.compile(
    r'<span[^>]*class="[^"]*s-item__price[^"]*"[^>]*>(.*?)</span>',
    re.DOTALL,
)
_LINK_RE = re.compile(r'<a[^>]*href="([^"]*ebay\.[^"]*itm[^"]*)"', re.DOTALL)


@dataclass
class SoldItem:
    """A single sold listing from eBay."""

    title: str
    price: float
    currency: str
    price_eur: float
    url: str
    sold_date: str | None = None
    category: str | None = None


def _parse_price(text: str, currency: str) -> float | None:
    """Extract numeric price from text like 'EUR 12,99' or '$45.00'."""
    text = re.sub(r"<[^>]+>", "", text).strip()
    match = _PRICE_RE.search(text.replace(".", "").replace(",", "."))
    if not match:
        # Try alternative: keep dots as decimals
        cleaned = text.replace(",", "")
        match = _PRICE_RE.search(cleaned)
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None
    return None


def _to_eur(price: float, currency: str, rates: dict[str, float] | None = None) -> float:
    """Convert price to EUR."""
    rates = rates or DEFAULT_EXCHANGE_RATES
    rate = rates.get(currency, 1.0)
    return round(price * rate, 2)


async def scrape_sold_listings(
    region: EbayRegion,
    query: str,
    config: ScannerConfig,
    max_pages: int | None = None,
) -> list[SoldItem]:
    """Scrape sold/completed listings from an eBay region."""
    max_pages = max_pages or config.max_pages_per_query
    items: list[SoldItem] = []

    headers = {
        "User-Agent": config.user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
    }

    async with httpx.AsyncClient(
        headers=headers,
        follow_redirects=True,
        timeout=30.0,
    ) as client:
        for page in range(1, max_pages + 1):
            url = region.sold_url(query, page=page)
            logger.info("Scraping %s page %d: %s", region.name, page, url)

            try:
                resp = await client.get(url)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                logger.warning("HTTP error scraping %s: %s", url, e)
                break

            html = resp.text
            page_items = _parse_listings(html, region.currency)
            if not page_items:
                break

            items.extend(page_items)
            await asyncio.sleep(config.scrape_delay_sec)

    logger.info("Scraped %d items from %s for '%s'", len(items), region.name, query)
    return items


def _parse_listings(html: str, currency: str) -> list[SoldItem]:
    """Parse sold listings from eBay HTML."""
    items: list[SoldItem] = []

    blocks = _ITEM_BLOCK_RE.findall(html)
    for block in blocks:
        title_match = _TITLE_RE.search(block)
        price_match = _PRICE_TAG_RE.search(block)
        link_match = _LINK_RE.search(block)

        if not title_match or not price_match:
            continue

        title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip()
        if not title or title.lower().startswith("shop on ebay"):
            continue

        price = _parse_price(price_match.group(1), currency)
        if price is None or price <= 0:
            continue

        url = link_match.group(1) if link_match else ""
        price_eur = _to_eur(price, currency)

        items.append(
            SoldItem(
                title=title,
                price=price,
                currency=currency,
                price_eur=price_eur,
                url=url,
                sold_date=datetime.utcnow().strftime("%Y-%m-%d"),
            )
        )

    return items


async def fetch_exchange_rates() -> dict[str, float]:
    """Fetch current exchange rates to EUR from a free API."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.exchangerate-api.com/v4/latest/EUR"
            )
            resp.raise_for_status()
            data = resp.json()
            # We need rates as "1 CURRENCY = X EUR", so invert
            return {
                code: round(1.0 / rate, 6)
                for code, rate in data.get("rates", {}).items()
            }
    except Exception as e:
        logger.warning("Failed to fetch exchange rates: %s – using defaults", e)
        return DEFAULT_EXCHANGE_RATES
