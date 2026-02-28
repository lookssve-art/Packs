"""Odds shift timeline — shows how drop rates change over time."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from config.constants import RARITY_ORDER
from src.models.dataclasses import DropRateSnapshot


def render_odds_shift(
    snapshots_by_pack: dict[str, list[DropRateSnapshot]],
) -> None:
    """Render odds shift timeline chart."""
    st.subheader("Odds Shift Timeline")

    if not snapshots_by_pack:
        st.info("No odds shift data yet. Snapshots will appear as drop rates are tracked.")
        return

    for pack_type, snapshots in snapshots_by_pack.items():
        if len(snapshots) < 2:
            continue

        st.markdown(f"**{pack_type.title()}**")

        # Sort by timestamp
        sorted_snaps = sorted(snapshots, key=lambda s: s.timestamp)
        timestamps = [s.timestamp for s in sorted_snaps]

        fig = go.Figure()
        colors = {"holographic": "#f38ba8", "gold": "#f9e2af",
                  "silver": "#a6adc8", "gloss": "#585b70"}

        for rarity in RARITY_ORDER:
            rates = [s.rates.get(rarity, 0.0) * 100 for s in sorted_snaps]
            fig.add_trace(go.Scatter(
                x=timestamps,
                y=rates,
                name=rarity.title(),
                mode="lines+markers",
                line=dict(color=colors.get(rarity, "#cdd6f4"), width=2),
                marker=dict(size=6),
            ))

        fig.update_layout(
            yaxis_title="Drop Rate (%)",
            xaxis_title="Time",
            height=300,
            margin=dict(t=20, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#cdd6f4"),
        )

        st.plotly_chart(fig, use_container_width=True)
