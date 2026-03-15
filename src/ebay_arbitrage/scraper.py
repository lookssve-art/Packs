"""eBay sold-listings scraper with bot-evasion headers + demo mode."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import re
from dataclasses import dataclass
from datetime import datetime

import httpx

from .config import DEFAULT_EXCHANGE_RATES, EbayRegion, ScannerConfig

logger = logging.getLogger(__name__)

# Regex patterns for parsing eBay sold listings HTML
_PRICE_RE = re.compile(r"[\d.,]+")
_ITEM_BLOCK_RE = re.compile(
    r'<li[^>]*class="[^"]*s-item\b[^"]*"[^>]*>(.*?)</li>',
    re.DOTALL,
)
_TITLE_RE = re.compile(
    r'class="[^"]*s-item__title[^"]*"[^>]*>(?:<span[^>]*>)?\s*(.*?)\s*(?:</span>)?</',
    re.DOTALL,
)
_PRICE_TAG_RE = re.compile(
    r'class="[^"]*s-item__price[^"]*"[^>]*>(.*?)</span>',
    re.DOTALL,
)
_LINK_RE = re.compile(r'href="(https?://www\.ebay\.[^"]*?/itm/[^"]*)"')


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


# ---------------------------------------------------------------------------
# Browser-like request headers to reduce bot detection
# ---------------------------------------------------------------------------

_CHROME_HEADERS = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7"
    ),
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
    "Cache-Control": "max-age=0",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}


def _parse_price(text: str, currency: str) -> float | None:
    """Extract numeric price from text like 'EUR 12,99' or '$45.00'."""
    text = re.sub(r"<[^>]+>", "", text).strip()
    # Remove currency symbols/words
    text = re.sub(r"(EUR|USD|JPY|\$|¥|€)", "", text).strip()

    if not text:
        return None

    # German format: 1.234,56  →  1234.56
    if "," in text and "." in text:
        if text.rindex(",") > text.rindex("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")

    match = _PRICE_RE.search(text)
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
    """Scrape sold/completed listings from an eBay region.

    Falls back to demo data when ``config.demo_mode`` is True or when
    scraping fails (useful for testing the full pipeline).
    """
    if getattr(config, "demo_mode", False):
        return _generate_demo_items(region, query)

    max_pages = max_pages or config.max_pages_per_query
    items: list[SoldItem] = []

    async with httpx.AsyncClient(
        headers=_CHROME_HEADERS,
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
                logger.debug("No items parsed from page %d", page)
                break

            items.extend(page_items)
            # Randomized delay to look more human
            delay = config.scrape_delay_sec + random.uniform(0.5, 1.5)
            await asyncio.sleep(delay)

    if not items:
        logger.info(
            "Live scraping returned 0 items for '%s' on %s – "
            "this may be due to bot detection or network restrictions",
            query, region.name,
        )

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
            return {
                code: round(1.0 / rate, 6)
                for code, rate in data.get("rates", {}).items()
            }
    except Exception as e:
        logger.warning("Failed to fetch exchange rates: %s – using defaults", e)
        return DEFAULT_EXCHANGE_RATES


# ---------------------------------------------------------------------------
# Demo / seed data for testing the full pipeline without live eBay access
# ---------------------------------------------------------------------------

_DEMO_CATALOG: dict[str, dict] = {
    "pokemon karten": {
        "de": [("Pokemon Glurak VMAX Alt Art", 185), ("Pokemon Booster Display 151", 145),
               ("Charizard ex SAR Japanese", 120), ("Pokemon Trainer Gallery Set", 65),
               ("Mew VMAX Gold Secret", 42), ("Pikachu VMAX Rainbow", 38)],
        "us": [("Pokemon Charizard VMAX Alt Art", 140), ("Pokemon 151 Booster Box", 108),
               ("Charizard ex SAR Japanese", 78), ("Pokemon Trainer Gallery Set", 45),
               ("Mew VMAX Gold Secret", 28), ("Pikachu VMAX Rainbow", 24)],
        "jp": [("ポケモン リザードン VMAX SA", 65), ("ポケモン 151 BOX", 48),
               ("リザードン ex SAR", 42), ("ポケモン トレーナーズ", 22),
               ("ミュウ VMAX UR", 15), ("ピカチュウ VMAX HR", 12)],
        "cn": [("Pokemon Charizard VMAX Chinese", 55), ("Pokemon 151 CN Booster", 38),
               ("Charizard ex SAR CN", 35), ("Pokemon Trainer Gallery CN", 18),
               ("Mew VMAX Gold CN", 12), ("Pikachu VMAX CN", 10)],
    },
    "iphone": {
        "de": [("iPhone 15 Pro Max 256GB", 1050), ("iPhone 14 Pro 128GB", 720),
               ("iPhone 13 128GB", 450), ("iPhone 12 64GB", 310)],
        "us": [("iPhone 15 Pro Max 256GB", 920), ("iPhone 14 Pro 128GB", 610),
               ("iPhone 13 128GB", 380), ("iPhone 12 64GB", 255)],
        "jp": [("iPhone 15 Pro Max 256GB", 880), ("iPhone 14 Pro 128GB", 580),
               ("iPhone 13 128GB", 350), ("iPhone 12 64GB", 240)],
        "cn": [("iPhone 15 Pro Max 256GB", 850), ("iPhone 14 Pro 128GB", 545),
               ("iPhone 13 128GB", 320), ("iPhone 12 64GB", 215)],
    },
    "nintendo switch": {
        "de": [("Nintendo Switch OLED", 285), ("Switch Lite", 155),
               ("Switch Pro Controller", 52), ("Switch Dock", 45)],
        "us": [("Nintendo Switch OLED", 250), ("Switch Lite", 130),
               ("Switch Pro Controller", 42), ("Switch Dock", 35)],
        "jp": [("Nintendo Switch 有機EL", 215), ("Switch Lite", 105),
               ("Switch Pro Controller", 35), ("Switch Dock", 28)],
        "cn": [("Nintendo Switch OLED CN", 230), ("Switch Lite CN", 115),
               ("Switch Pro Controller CN", 32), ("Switch Dock CN", 25)],
    },
    "lego": {
        "de": [("LEGO Technic 42151 Bugatti", 385), ("LEGO Star Wars 75192 Falcon", 680),
               ("LEGO Icons 10307 Eiffelturm", 520), ("LEGO City 60337 Zug", 125)],
        "us": [("LEGO Technic 42151 Bugatti", 350), ("LEGO Star Wars 75192 Falcon", 620),
               ("LEGO Icons 10307 Eiffel Tower", 470), ("LEGO City 60337 Express", 105)],
        "jp": [("LEGO テクニック 42151", 360), ("LEGO スターウォーズ 75192", 640),
               ("LEGO 10307 エッフェル塔", 490), ("LEGO シティ 60337", 110)],
        "cn": [("LEGO Technic 42151 CN", 280), ("LEGO Star Wars 75192 CN", 510),
               ("LEGO Icons 10307 CN", 380), ("LEGO City 60337 CN", 82)],
    },
    "playstation 5": {
        "de": [("PS5 Digital Edition", 380), ("PS5 Disc Edition", 445),
               ("PS5 DualSense Controller", 55), ("PS5 Pulse 3D Headset", 68)],
        "us": [("PS5 Digital Edition", 340), ("PS5 Disc Edition", 400),
               ("DualSense Controller", 45), ("Pulse 3D Headset", 55)],
        "jp": [("PS5 デジタルエディション", 320), ("PS5 ディスクエディション", 385),
               ("DualSense コントローラー", 38), ("Pulse 3D ヘッドセット", 48)],
        "cn": [("PS5 Digital CN", 310), ("PS5 Disc CN", 370),
               ("DualSense CN", 32), ("Pulse 3D CN", 42)],
    },
    "magic the gathering": {
        "de": [("MTG The One Ring Foil", 520), ("Black Lotus Replica", 285),
               ("MTG Commander Masters Box", 195), ("Sheoldred Promo Foil", 45)],
        "us": [("MTG The One Ring Foil", 440), ("Black Lotus Replica", 230),
               ("Commander Masters Box", 165), ("Sheoldred Promo Foil", 32)],
        "jp": [("MTG 一つの指輪 Foil JP", 350), ("MTG ブラックロータス", 195),
               ("統率者マスターズ BOX", 130), ("シェオルドレッド JP", 22)],
        "cn": [("MTG The One Ring CN", 380), ("Black Lotus CN", 210),
               ("Commander Masters CN", 145), ("Sheoldred CN", 28)],
    },
    "yu-gi-oh": {
        "de": [("Yu-Gi-Oh Blue Eyes Ultimate PSA 10", 320), ("Pot of Greed 1st Ed", 155),
               ("Dark Magician Girl Secret", 88), ("Starlight Rare Ash Blossom", 195)],
        "us": [("Blue Eyes Ultimate PSA 10", 270), ("Pot of Greed 1st Ed", 125),
               ("Dark Magician Girl Secret", 68), ("Starlight Ash Blossom", 160)],
        "jp": [("青眼の究極竜 PSA10", 180), ("強欲な壺 初期", 85),
               ("ブラマジガール シークレット", 42), ("灰流うらら スターライト", 95)],
        "cn": [("Blue Eyes Ultimate CN", 210), ("Pot of Greed CN", 95),
               ("Dark Magician Girl CN", 50), ("Ash Blossom Starlight CN", 120)],
    },
    "anime figur": {
        "de": [("Figma Gojo Satoru", 85), ("Nendoroid Tanjiro", 55),
               ("Banpresto Goku Ultra Instinct", 42), ("Prize Figure Anya Forger", 35)],
        "us": [("Figma Gojo Satoru", 70), ("Nendoroid Tanjiro", 42),
               ("Banpresto Goku Ultra Instinct", 32), ("Prize Figure Anya", 28)],
        "jp": [("フィグマ 五条悟", 38), ("ねんどろいど 炭治郎", 22),
               ("バンプレスト 悟空", 15), ("プライズ アーニャ", 12)],
        "cn": [("Figma Gojo CN", 42), ("Nendoroid Tanjiro CN", 25),
               ("Banpresto Goku CN", 18), ("Prize Figure Anya CN", 14)],
    },
    "dyson": {
        "de": [("Dyson V15 Detect", 480), ("Dyson Airwrap Complete", 420),
               ("Dyson V12 Detect Slim", 365), ("Dyson Pure Cool", 295)],
        "us": [("Dyson V15 Detect", 410), ("Dyson Airwrap Complete", 360),
               ("Dyson V12 Detect Slim", 310), ("Dyson Pure Cool", 250)],
        "jp": [("Dyson V15 Detect JP", 395), ("Dyson Airwrap JP", 340),
               ("Dyson V12 JP", 295), ("Dyson Pure Cool JP", 235)],
        "cn": [("Dyson V15 Detect CN", 350), ("Dyson Airwrap CN", 300),
               ("Dyson V12 CN", 265), ("Dyson Pure Cool CN", 210)],
    },
    "rolex": {
        "de": [("Rolex Submariner Date 126610", 12800), ("Rolex Datejust 41", 9500),
               ("Rolex GMT-Master II", 15200), ("Rolex Explorer 124270", 7800)],
        "us": [("Rolex Submariner 126610", 11500), ("Rolex Datejust 41", 8400),
               ("Rolex GMT-Master II", 13800), ("Rolex Explorer 124270", 6900)],
        "jp": [("ロレックス サブマリーナ", 10800), ("ロレックス デイトジャスト", 7800),
               ("ロレックス GMTマスター", 12500), ("ロレックス エクスプローラー", 6400)],
        "cn": [("Rolex Submariner CN", 10200), ("Rolex Datejust CN", 7200),
               ("Rolex GMT-Master CN", 11800), ("Rolex Explorer CN", 5900)],
    },
    "samsung galaxy": {
        "de": [("Samsung Galaxy S24 Ultra", 880), ("Galaxy S23 128GB", 520),
               ("Galaxy Watch 6", 185), ("Galaxy Buds2 Pro", 95)],
        "us": [("Samsung Galaxy S24 Ultra", 780), ("Galaxy S23 128GB", 440),
               ("Galaxy Watch 6", 155), ("Galaxy Buds2 Pro", 78)],
        "jp": [("Galaxy S24 Ultra JP", 750), ("Galaxy S23 JP", 415),
               ("Galaxy Watch 6 JP", 140), ("Galaxy Buds2 Pro JP", 68)],
        "cn": [("Samsung Galaxy S24 Ultra CN", 680), ("Galaxy S23 CN", 375),
               ("Galaxy Watch 6 CN", 120), ("Galaxy Buds2 Pro CN", 55)],
    },
    "airpods": {
        "de": [("AirPods Pro 2 USB-C", 195), ("AirPods 3. Gen", 145),
               ("AirPods Max", 420), ("AirPods Pro 1. Gen", 115)],
        "us": [("AirPods Pro 2 USB-C", 168), ("AirPods 3rd Gen", 125),
               ("AirPods Max", 370), ("AirPods Pro 1st Gen", 95)],
        "jp": [("AirPods Pro 2 JP", 155), ("AirPods 3 JP", 112),
               ("AirPods Max JP", 345), ("AirPods Pro 1 JP", 85)],
        "cn": [("AirPods Pro 2 CN", 135), ("AirPods 3 CN", 98),
               ("AirPods Max CN", 310), ("AirPods Pro 1 CN", 72)],
    },
    "nike jordan": {
        "de": [("Air Jordan 1 Retro High OG", 220), ("Air Jordan 4 Retro", 265),
               ("Air Jordan 11 Cherry", 195), ("Jordan 1 Low", 125)],
        "us": [("Air Jordan 1 Retro High OG", 180), ("Air Jordan 4 Retro", 225),
               ("Air Jordan 11 Cherry", 165), ("Jordan 1 Low", 100)],
        "jp": [("Air Jordan 1 Retro JP", 165), ("Air Jordan 4 JP", 210),
               ("Air Jordan 11 Cherry JP", 150), ("Jordan 1 Low JP", 90)],
        "cn": [("Air Jordan 1 Retro CN", 120), ("Air Jordan 4 CN", 165),
               ("Air Jordan 11 Cherry CN", 115), ("Jordan 1 Low CN", 68)],
    },
    "gpu grafikkarte": {
        "de": [("RTX 4090 24GB", 1650), ("RTX 4070 Ti Super", 720),
               ("RX 7900 XTX", 820), ("RTX 4060 Ti", 380)],
        "us": [("RTX 4090 24GB", 1480), ("RTX 4070 Ti Super", 620),
               ("RX 7900 XTX", 720), ("RTX 4060 Ti", 330)],
        "jp": [("RTX 4090 24GB JP", 1520), ("RTX 4070 Ti Super JP", 650),
               ("RX 7900 XTX JP", 750), ("RTX 4060 Ti JP", 345)],
        "cn": [("RTX 4090 24GB CN", 1350), ("RTX 4070 Ti Super CN", 560),
               ("RX 7900 XTX CN", 640), ("RTX 4060 Ti CN", 290)],
    },
    "manga": {
        "de": [("One Piece Box Set 1-23", 165), ("Berserk Deluxe Edition 1", 42),
               ("Chainsaw Man 1-12 Set", 95), ("Jujutsu Kaisen 0-20", 155)],
        "us": [("One Piece Box Set 1-23", 135), ("Berserk Deluxe 1", 34),
               ("Chainsaw Man 1-12", 78), ("Jujutsu Kaisen 0-20", 128)],
        "jp": [("ワンピース 1-23巻", 45), ("ベルセルク デラックス", 18),
               ("チェンソーマン 1-12", 32), ("呪術廻戦 0-20", 48)],
        "cn": [("One Piece Box 1-23 CN", 52), ("Berserk Deluxe CN", 20),
               ("Chainsaw Man 1-12 CN", 38), ("Jujutsu Kaisen 0-20 CN", 55)],
    },
    "funko pop": {
        "de": [("Funko Pop Goku #14 Vaulted", 85), ("Funko Pop Batman #01", 145),
               ("Funko Pop Naruto Six Path", 42), ("Funko Pop Pikachu #353", 32)],
        "us": [("Funko Pop Goku #14", 68), ("Funko Pop Batman #01", 118),
               ("Funko Pop Naruto Six Path", 32), ("Funko Pop Pikachu #353", 24)],
        "jp": [("Funko Pop 悟空 #14", 52), ("Funko Pop バットマン #01", 95),
               ("Funko Pop ナルト", 25), ("Funko Pop ピカチュウ", 18)],
        "cn": [("Funko Pop Goku CN", 38), ("Funko Pop Batman CN", 72),
               ("Funko Pop Naruto CN", 18), ("Funko Pop Pikachu CN", 12)],
    },
    "sony kamera": {
        "de": [("Sony A7 IV Body", 1850), ("Sony A6400 Kit", 720),
               ("Sony FE 24-70mm f/2.8", 1680), ("Sony ZV-E10", 580)],
        "us": [("Sony A7 IV Body", 1650), ("Sony A6400 Kit", 620),
               ("Sony FE 24-70mm f/2.8", 1520), ("Sony ZV-E10", 495)],
        "jp": [("Sony A7 IV ボディ", 1480), ("Sony A6400 キット", 545),
               ("Sony FE 24-70mm f/2.8", 1380), ("Sony ZV-E10 JP", 435)],
        "cn": [("Sony A7 IV CN", 1420), ("Sony A6400 CN", 510),
               ("Sony FE 24-70mm CN", 1320), ("Sony ZV-E10 CN", 405)],
    },
    "macbook": {
        "de": [("MacBook Pro 14 M3 Pro", 1850), ("MacBook Air M2 13", 980),
               ("MacBook Pro 16 M3 Max", 3200), ("MacBook Air M1", 650)],
        "us": [("MacBook Pro 14 M3 Pro", 1650), ("MacBook Air M2 13", 850),
               ("MacBook Pro 16 M3 Max", 2880), ("MacBook Air M1", 560)],
        "jp": [("MacBook Pro 14 M3 Pro JP", 1580), ("MacBook Air M2 JP", 810),
               ("MacBook Pro 16 M3 Max JP", 2750), ("MacBook Air M1 JP", 520)],
        "cn": [("MacBook Pro 14 M3 Pro CN", 1520), ("MacBook Air M2 CN", 775),
               ("MacBook Pro 16 M3 Max CN", 2650), ("MacBook Air M1 CN", 485)],
    },
    "vintage uhr": {
        "de": [("Omega Seamaster 300 Vintage", 3800), ("Seiko 6139 Chronograph", 680),
               ("Casio G-Shock DW-5000 1983", 1250), ("Citizen Promaster Vintage", 320)],
        "us": [("Omega Seamaster 300 Vintage", 3200), ("Seiko 6139 Chrono", 520),
               ("Casio G-Shock DW-5000", 980), ("Citizen Promaster Vintage", 245)],
        "jp": [("オメガ シーマスター 300", 2850), ("セイコー 6139", 380),
               ("カシオ G-Shock DW-5000", 750), ("シチズン プロマスター", 185)],
        "cn": [("Omega Seamaster 300 CN", 2650), ("Seiko 6139 CN", 340),
               ("Casio G-Shock DW-5000 CN", 680), ("Citizen Promaster CN", 165)],
    },
    "retro konsole": {
        "de": [("Nintendo 64 Konsole komplett", 125), ("Super Nintendo SNES", 105),
               ("Sega Mega Drive", 85), ("Game Boy Color", 72)],
        "us": [("Nintendo 64 Console Complete", 95), ("Super Nintendo SNES", 80),
               ("Sega Genesis", 62), ("Game Boy Color", 55)],
        "jp": [("ニンテンドー64 本体", 52), ("スーパーファミコン", 42),
               ("メガドライブ", 35), ("ゲームボーイカラー", 28)],
        "cn": [("Nintendo 64 CN", 58), ("Super Nintendo CN", 48),
               ("Sega Mega Drive CN", 38), ("Game Boy Color CN", 32)],
    },
    "steiff": {
        "de": [("Steiff Teddybär 1950 Original", 450), ("Steiff Elefant vintage", 185),
               ("Steiff Hase Niki 28cm", 65), ("Steiff Katze Lizzy", 48)],
        "us": [("Steiff Teddy Bear 1950", 320), ("Steiff Elephant vintage", 135),
               ("Steiff Rabbit Niki", 42), ("Steiff Cat Lizzy", 32)],
        "jp": [("シュタイフ テディベア 1950", 280), ("シュタイフ エレファント", 115),
               ("シュタイフ うさぎ", 35), ("シュタイフ 猫", 28)],
        "cn": [("Steiff Teddy 1950 CN", 250), ("Steiff Elephant CN", 98),
               ("Steiff Rabbit CN", 30), ("Steiff Cat CN", 22)],
    },
    "bose kopfhörer": {
        "de": [("Bose QC Ultra Headphones", 320), ("Bose QC45", 195),
               ("Bose 700", 225), ("Bose Sport Earbuds", 95)],
        "us": [("Bose QC Ultra", 275), ("Bose QC45", 165),
               ("Bose 700", 190), ("Bose Sport Earbuds", 78)],
        "jp": [("Bose QC Ultra JP", 260), ("Bose QC45 JP", 150),
               ("Bose 700 JP", 175), ("Bose Sport Earbuds JP", 68)],
        "cn": [("Bose QC Ultra CN", 235), ("Bose QC45 CN", 130),
               ("Bose 700 CN", 155), ("Bose Sport Earbuds CN", 55)],
    },
    "swatch": {
        "de": [("Swatch x Omega MoonSwatch Saturn", 320), ("MoonSwatch Mission to Mars", 285),
               ("Swatch Sistem51", 145), ("Swatch Originals Classic", 65)],
        "us": [("MoonSwatch Mission to Saturn", 265), ("MoonSwatch Mission to Mars", 240),
               ("Swatch Sistem51", 120), ("Swatch Originals", 52)],
        "jp": [("MoonSwatch Saturn JP", 245), ("MoonSwatch Mars JP", 215),
               ("Swatch Sistem51 JP", 105), ("Swatch Classic JP", 42)],
        "cn": [("MoonSwatch Saturn CN", 210), ("MoonSwatch Mars CN", 185),
               ("Swatch Sistem51 CN", 88), ("Swatch Classic CN", 35)],
    },
    "montblanc": {
        "de": [("Montblanc Meisterstück 149", 385), ("Montblanc StarWalker", 245),
               ("Montblanc Kugelschreiber", 165), ("Montblanc Etui Leder", 120)],
        "us": [("Montblanc Meisterstück 149", 320), ("Montblanc StarWalker", 195),
               ("Montblanc Ballpoint", 135), ("Montblanc Leather Case", 95)],
        "jp": [("モンブラン マイスターシュテュック", 295), ("モンブラン スターウォーカー", 178),
               ("モンブラン ボールペン", 118), ("モンブラン レザーケース", 82)],
        "cn": [("Montblanc 149 CN", 265), ("Montblanc StarWalker CN", 158),
               ("Montblanc Ballpoint CN", 102), ("Montblanc Case CN", 68)],
    },
    "leica": {
        "de": [("Leica M10 Body", 4500), ("Leica Q3", 5200),
               ("Leica Summicron 50mm", 1850), ("Leica CL", 1650)],
        "us": [("Leica M10 Body", 3900), ("Leica Q3", 4600),
               ("Leica Summicron 50mm", 1580), ("Leica CL", 1380)],
        "jp": [("ライカ M10 ボディ", 3500), ("ライカ Q3", 4200),
               ("ライカ Summicron 50mm", 1380), ("ライカ CL", 1220)],
        "cn": [("Leica M10 CN", 3300), ("Leica Q3 CN", 3950),
               ("Leica Summicron CN", 1280), ("Leica CL CN", 1120)],
    },
    "playmobil": {
        "de": [("Playmobil 70220 Novelmore Burg", 95), ("Playmobil 9462 Feuerwehr", 68),
               ("Playmobil 70190 Krankenhaus", 85), ("Playmobil Country Bauernhof", 52)],
        "us": [("Playmobil 70220 Novelmore Castle", 72), ("Playmobil 9462 Fire Station", 48),
               ("Playmobil 70190 Hospital", 62), ("Playmobil Country Farm", 38)],
        "jp": [("プレイモービル 70220", 68), ("プレイモービル 9462", 45),
               ("プレイモービル 70190", 58), ("プレイモービル 農場", 35)],
        "cn": [("Playmobil 70220 CN", 48), ("Playmobil 9462 CN", 32),
               ("Playmobil 70190 CN", 42), ("Playmobil Farm CN", 25)],
    },
    "ravensburger puzzle": {
        "de": [("Ravensburger 9000 Teile Astrologer", 85), ("Ravensburger 3D Eiffelturm", 38),
               ("Ravensburger Disney 40320", 295), ("Ravensburger Exit Puzzle", 15)],
        "us": [("Ravensburger 9000pc Astrologer", 65), ("Ravensburger 3D Eiffel", 28),
               ("Ravensburger Disney 40320", 245), ("Ravensburger Exit Puzzle", 10)],
        "jp": [("ラベンスバーガー 9000ピース", 72), ("ラベンスバーガー 3D エッフェル", 32),
               ("ラベンスバーガー ディズニー 40320", 260), ("ラベンスバーガー Exit", 12)],
        "cn": [("Ravensburger 9000 CN", 48), ("Ravensburger 3D CN", 18),
               ("Ravensburger Disney 40320 CN", 195), ("Ravensburger Exit CN", 7)],
    },
    "kindle": {
        "de": [("Kindle Paperwhite 11. Gen", 125), ("Kindle Oasis 3", 195),
               ("Kindle Scribe", 285), ("Kindle Basic 2022", 75)],
        "us": [("Kindle Paperwhite 11th Gen", 105), ("Kindle Oasis 3", 168),
               ("Kindle Scribe", 245), ("Kindle Basic 2022", 60)],
        "jp": [("Kindle Paperwhite 11 JP", 95), ("Kindle Oasis 3 JP", 152),
               ("Kindle Scribe JP", 228), ("Kindle Basic JP", 52)],
        "cn": [("Kindle Paperwhite CN", 82), ("Kindle Oasis CN", 135),
               ("Kindle Scribe CN", 205), ("Kindle Basic CN", 42)],
    },
    "gopro": {
        "de": [("GoPro Hero 12 Black", 345), ("GoPro Hero 11", 265),
               ("GoPro Max 360", 385), ("GoPro Hero 10", 195)],
        "us": [("GoPro Hero 12 Black", 295), ("GoPro Hero 11", 225),
               ("GoPro Max 360", 335), ("GoPro Hero 10", 165)],
        "jp": [("GoPro Hero 12 JP", 280), ("GoPro Hero 11 JP", 210),
               ("GoPro Max 360 JP", 315), ("GoPro Hero 10 JP", 148)],
        "cn": [("GoPro Hero 12 CN", 248), ("GoPro Hero 11 CN", 190),
               ("GoPro Max 360 CN", 285), ("GoPro Hero 10 CN", 132)],
    },
    "thermomix": {
        "de": [("Thermomix TM6", 1050), ("Thermomix TM5", 520),
               ("Thermomix Cook-Key", 85), ("Thermomix Varoma", 65)],
        "us": [("Thermomix TM6", 1150), ("Thermomix TM5", 580),
               ("Thermomix Cook-Key", 95), ("Thermomix Varoma", 75)],
        "jp": [("Thermomix TM6 JP", 1200), ("Thermomix TM5 JP", 620),
               ("Thermomix Cook-Key JP", 105), ("Thermomix Varoma JP", 82)],
        "cn": [("Thermomix TM6 CN", 880), ("Thermomix TM5 CN", 420),
               ("Thermomix Cook-Key CN", 55), ("Thermomix Varoma CN", 42)],
    },
}


def _generate_demo_items(region: EbayRegion, query: str) -> list[SoldItem]:
    """Generate realistic demo items for a given region and query."""
    query_lower = query.lower()
    catalog_key = None
    for key in _DEMO_CATALOG:
        if key in query_lower or query_lower in key:
            catalog_key = key
            break

    if not catalog_key:
        return []

    # Determine region key from the region object
    region_key = "de"
    for rk, rv in {
        "de": "ebay.de", "us": "ebay.com",
        "jp": "ebay.co.jp", "cn": "ebay.com",
    }.items():
        if rv in region.base_url:
            region_key = rk
            break
    # Special handling for CN (both CN and US use ebay.com)
    if "PrefLoc" in region.sold_path:
        region_key = "cn"

    items_data = _DEMO_CATALOG[catalog_key].get(region_key, [])

    items = []
    for title, price_eur in items_data:
        # Add slight randomness (+-5%) to simulate real variation
        seed = int(hashlib.md5(f"{title}{region_key}".encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        variation = rng.uniform(0.95, 1.05)
        actual_price_eur = round(price_eur * variation, 2)

        # Convert back to local currency for display
        rate = DEFAULT_EXCHANGE_RATES.get(region.currency, 1.0)
        local_price = round(actual_price_eur / rate, 2) if rate else actual_price_eur

        items.append(
            SoldItem(
                title=title,
                price=local_price,
                currency=region.currency,
                price_eur=actual_price_eur,
                url=f"{region.base_url}/itm/demo-{hashlib.md5(title.encode()).hexdigest()[:12]}",
                sold_date=datetime.utcnow().strftime("%Y-%m-%d"),
            )
        )

    return items
