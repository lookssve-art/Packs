"""Odds comparison chart — published vs observed drop rates."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from config.constants import RARITY_ORDER
from src.models.dataclasses import DropRateSnapshot, EVResult


def render_odds_comparison(
    ev_results: list[EVResult],
    published_snapshots: dict[str, DropRateSnapshot],
) -> None:
    """Render grouped bar chart comparing published vs observed odds."""
    st.subheader("Odds Comparison: Published vs Observed")

    if not ev_results:
        st.info("Not enough data yet.")
        return

    for ev in ev_results:
        st.markdown(f"**{ev.pack_type.title()}**")

        published = published_snapshots.get(ev.pack_type)
        rarities = RARITY_ORDER

        # Published rates
        pub_rates = []
        obs_rates = []
        obs_lower = []
        obs_upper = []
        labels = []

        for r in rarities:
            labels.append(r.title())
            pub_rates.append(
                published.rates.get(r, 0.0) * 100 if published else 0.0
            )
            mean, lower, upper = ev.rarity_posteriors.get(r, (0.0, 0.0, 0.0))
            obs_rates.append(mean * 100)
            obs_lower.append(lower * 100)
            obs_upper.append(upper * 100)

        fig = go.Figure()

        if published:
            fig.add_trace(go.Bar(
                name="Published",
                x=labels,
                y=pub_rates,
                marker_color="#89b4fa",
                opacity=0.8,
            ))

        fig.add_trace(go.Bar(
            name="Observed (posterior mean)",
            x=labels,
            y=obs_rates,
            marker_color="#a6e3a1",
            opacity=0.8,
            error_y=dict(
                type="data",
                symmetric=False,
                array=[u - m for u, m in zip(obs_upper, obs_rates)],
                arrayminus=[m - l for m, l in zip(obs_rates, obs_lower)],
                visible=True,
            ),
        ))

        fig.update_layout(
            barmode="group",
            yaxis_title="Probability (%)",
            height=350,
            margin=dict(t=20, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#cdd6f4"),
        )

        st.plotly_chart(fig, use_container_width=True)

        # Show confidence info
        st.caption(
            f"Based on {ev.obs_count} observations | "
            f"Confidence: {ev.confidence_tier.replace('_', ' ').title()} | "
            f"Model: {ev.model_mode.upper()}"
        )
