"""Trend charts over time — EV, EV Ratio, observation count."""

from __future__ import annotations

import json

import plotly.graph_objects as go
import streamlit as st


def render_ev_trend(
    ev_history: dict[str, list[dict]],
) -> None:
    """Render EV and EV Ratio trend lines over time."""
    st.subheader("EV Trend Over Time")

    if not ev_history:
        st.info("Not enough historical data for trends yet.")
        return

    # EV Ratio trend
    fig = go.Figure()
    colors = ["#89b4fa", "#a6e3a1", "#f9e2af", "#f38ba8", "#cba6f7"]

    for i, (pack_type, history) in enumerate(ev_history.items()):
        if not history:
            continue
        timestamps = [h["timestamp"] for h in history]
        ev_ratios = [h["ev_ratio"] for h in history]

        fig.add_trace(go.Scatter(
            x=timestamps,
            y=ev_ratios,
            name=f"{pack_type.title()} EV Ratio",
            mode="lines",
            line=dict(color=colors[i % len(colors)], width=2),
        ))

    # Add reference line at 1.0 (break-even)
    fig.add_hline(
        y=1.0,
        line_dash="dash",
        line_color="#f38ba8",
        annotation_text="Break Even (1.0)",
    )

    fig.update_layout(
        yaxis_title="EV Ratio",
        xaxis_title="Time",
        height=350,
        margin=dict(t=20, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#cdd6f4"),
    )

    st.plotly_chart(fig, use_container_width=True)

    # EV absolute value trend
    fig2 = go.Figure()
    for i, (pack_type, history) in enumerate(ev_history.items()):
        if not history:
            continue
        timestamps = [h["timestamp"] for h in history]
        evs = [h["ev_value"] for h in history]
        costs = [h["pack_cost"] for h in history]

        fig2.add_trace(go.Scatter(
            x=timestamps,
            y=evs,
            name=f"{pack_type.title()} EV ($)",
            mode="lines",
            line=dict(color=colors[i % len(colors)], width=2),
        ))
        # Pack cost as horizontal line
        if costs:
            fig2.add_hline(
                y=costs[0],
                line_dash="dot",
                line_color=colors[i % len(colors)],
                opacity=0.5,
                annotation_text=f"{pack_type.title()} Cost",
            )

    fig2.update_layout(
        yaxis_title="Expected Value ($)",
        xaxis_title="Time",
        height=300,
        margin=dict(t=20, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#cdd6f4"),
    )

    st.plotly_chart(fig2, use_container_width=True)
