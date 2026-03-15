"""Discord webhook notifier for arbitrage opportunities."""

from __future__ import annotations

import logging
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

EMBED_COLOR_GREEN = 0x2ECC71
EMBED_COLOR_GOLD = 0xF1C40F


async def send_arbitrage_report(
    webhook_url: str,
    opportunities: list[dict],
    title: str | None = None,
) -> bool:
    """Send top arbitrage opportunities to Discord as an embed."""
    if not webhook_url:
        logger.warning("No Discord webhook URL configured – skipping notification")
        return False

    if not opportunities:
        logger.info("No opportunities to report")
        return False

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    title = title or f"eBay Arbitrage Report – {now}"

    # Build embed fields
    fields = []
    for i, opp in enumerate(opportunities[:10], 1):
        region_flag = {"us": "🇺🇸", "jp": "🇯🇵", "cn": "🇨🇳"}.get(
            opp["source_region"], "🌍"
        )
        fields.append(
            {
                "name": f"#{i} {opp['keyword']}",
                "value": (
                    f"{region_flag} **{opp['source_region'].upper()}** → **DE**\n"
                    f"Einkauf: €{opp['source_avg_price']:.2f} → Verkauf: €{opp['de_avg_price']:.2f}\n"
                    f"Profit: **€{opp['profit_eur']:.2f}** ({opp['margin_pct']:.0f}%)\n"
                    f"DE Verkäufe: {opp['de_sale_count']} | Quelle: {opp['source_sale_count']}"
                ),
                "inline": False,
            }
        )

    best = opportunities[0] if opportunities else None
    description = (
        f"Top {len(opportunities)} Arbitrage-Möglichkeiten gefunden.\n"
        f"Bester Deal: **{best['keyword']}** mit **{best['margin_pct']:.0f}%** Marge"
        if best
        else "Keine Opportunities gefunden."
    )

    payload = {
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": EMBED_COLOR_GOLD,
                "fields": fields,
                "footer": {"text": "eBay Arbitrage Scanner | Charizard Agent"},
                "timestamp": datetime.utcnow().isoformat(),
            }
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()
            logger.info("Discord report sent successfully")
            return True
    except httpx.HTTPError as e:
        logger.error("Failed to send Discord notification: %s", e)
        return False
