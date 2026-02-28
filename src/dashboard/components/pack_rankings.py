"""Pack ranking display component — shows 3 ranking modes."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.recommender.ranker import RankedPack, get_all_rankings
from src.models.dataclasses import EVResult


def render_pack_rankings(ev_results: list[EVResult]) -> None:
    """Render pack rankings in 3 modes side by side."""
    st.subheader("Pack Rankings")

    if not ev_results:
        st.info("Not enough data for rankings.")
        return

    rankings = get_all_rankings(ev_results)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("#### Best Rare+ Chance")
        _render_ranking_table(rankings["rare_plus"], "P(Rare+)")

    with col2:
        st.markdown("#### Best Super Rare")
        _render_ranking_table(rankings["super_rare"], "P(Holo)")

    with col3:
        st.markdown("#### Best EV Ratio")
        _render_ranking_table(rankings["ev_ratio"], "EV Ratio")


def _render_ranking_table(ranked: list[RankedPack], score_label: str) -> None:
    """Render a single ranking as a compact table."""
    if not ranked:
        st.caption("No data")
        return

    rows = []
    for rp in ranked:
        confidence_icon = {
            "calibrated": "",
            "partial": " ~",
            "very_conservative": " ?",
        }.get(rp.confidence_tier, "")

        rows.append({
            "#": rp.rank,
            "Pack": rp.pack_type.title(),
            score_label: rp.label + confidence_icon,
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True, height=150)
