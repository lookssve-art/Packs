"""Configuration for the eBay Arbitrage Scanner."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class EbayRegion:
    """eBay regional site configuration."""

    name: str
    base_url: str
    sold_path: str
    currency: str
    lang: str

    def sold_url(self, query: str, page: int = 1) -> str:
        """Build URL for completed/sold listings search."""
        import urllib.parse

        encoded = urllib.parse.quote_plus(query)
        return (
            f"{self.base_url}{self.sold_path}"
            f"&_nkw={encoded}&_pgn={page}&rt=nc&LH_Sold=1&LH_Complete=1"
        )


# Regional eBay configurations
REGIONS: dict[str, EbayRegion] = {
    "de": EbayRegion(
        name="Deutschland",
        base_url="https://www.ebay.de",
        sold_path="/sch/i.html?_sacat=0",
        currency="EUR",
        lang="de",
    ),
    "us": EbayRegion(
        name="USA",
        base_url="https://www.ebay.com",
        sold_path="/sch/i.html?_sacat=0",
        currency="USD",
        lang="en",
    ),
    "jp": EbayRegion(
        name="Japan",
        base_url="https://www.ebay.co.jp",
        sold_path="/sch/i.html?_sacat=0",
        currency="JPY",
        lang="ja",
    ),
    "cn": EbayRegion(
        name="China",
        base_url="https://www.ebay.com",
        sold_path="/sch/i.html?_sacat=0&LH_PrefLoc=2",  # items from China/HK
        currency="USD",
        lang="en",
    ),
}

# Exchange rates to EUR (updated periodically by the scanner)
DEFAULT_EXCHANGE_RATES: dict[str, float] = {
    "EUR": 1.0,
    "USD": 0.92,
    "JPY": 0.0061,
    "GBP": 1.16,
}


@dataclass
class ScannerConfig:
    """Global scanner configuration."""

    db_path: str = "ebay_arbitrage.db"
    discord_webhook_url: str = ""
    schedule_hours: list[int] = field(default_factory=lambda: [8, 20])
    top_n: int = 10
    min_profit_eur: float = 5.0
    min_margin_pct: float = 15.0
    max_pages_per_query: int = 3
    scrape_delay_sec: float = 1.5
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    def __post_init__(self) -> None:
        self.discord_webhook_url = os.environ.get(
            "EBAY_DISCORD_WEBHOOK", self.discord_webhook_url
        )
        db_env = os.environ.get("EBAY_ARBITRAGE_DB")
        if db_env:
            self.db_path = db_env
