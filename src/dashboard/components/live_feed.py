"""Live feed component — displays recent pulls in real-time."""

from __future__ import annotations

import datetime

import pandas as pd
import streamlit as st

from src.models.dataclasses import Pull


def render_live_feed(pulls: list[Pull], max_items: int = 30) -> None:
    """Render the live feed of recent pulls."""
    st.subheader("Live Feed — Recent Pulls")

    if not pulls:
        st.info("No pulls recorded yet. Waiting for data...")
        return

    display_pulls = pulls[:max_items]

    # Build dataframe
    rows = []
    now = datetime.datetime.utcnow()
    for p in display_pulls:
        age = now - p.timestamp
        if age.total_seconds() < 60:
            age_str = f"{int(age.total_seconds())}s ago"
        elif age.total_seconds() < 3600:
            age_str = f"{int(age.total_seconds() / 60)}m ago"
        elif age.total_seconds() < 86400:
            age_str = f"{int(age.total_seconds() / 3600)}h ago"
        else:
            age_str = f"{int(age.total_seconds() / 86400)}d ago"

        value_str = f"${p.estimated_value:.0f}" if p.estimated_value else "—"
        payout_str = f"${p.payout_value:.0f}" if p.payout_value else "—"

        rows.append({
            "Time": age_str,
            "Pack": p.pack_type.title(),
            "Card": p.card_name or "—",
            "Rarity": _rarity_badge(p.rarity),
            "Value": value_str,
            "Payout": payout_str,
        })

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=min(400, 40 + len(rows) * 35),
    )


def _rarity_badge(rarity: str) -> str:
    """Format rarity with visual indicator."""
    labels = {
        "epic": "Epic (1%)",
        "rare": "Rare (4%)",
        "uncommon": "Uncommon (15%)",
        "common": "Common (80%)",
    }
    return labels.get(rarity.lower(), rarity.upper())
