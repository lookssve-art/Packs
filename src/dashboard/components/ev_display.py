"""EV and EV Ratio display component."""

from __future__ import annotations

import streamlit as st

from src.models.dataclasses import EVResult


def render_ev_metrics(ev_results: list[EVResult]) -> None:
    """Render EV metrics as Streamlit metric cards."""
    if not ev_results:
        st.info("Waiting for data...")
        return

    cols = st.columns(len(ev_results))

    for i, ev in enumerate(ev_results):
        with cols[i]:
            st.markdown(f"### {ev.pack_type.title()} Pack")

            c1, c2 = st.columns(2)
            with c1:
                st.metric(
                    label="Expected Value",
                    value=f"${ev.ev:.2f}",
                )
                st.metric(
                    label="Pack Cost",
                    value=f"${ev.pack_cost:.0f}",
                )
            with c2:
                st.metric(
                    label="EV Ratio",
                    value=f"{ev.ev_ratio:.3f}",
                    delta="Positive EV!" if ev.ev_ratio >= 1.0 else None,
                    delta_color="normal" if ev.ev_ratio >= 1.0 else "off",
                )
                st.metric(
                    label="Observations",
                    value=str(ev.obs_count),
                )

            # Confidence badge
            confidence_colors = {
                "calibrated": "green",
                "partial": "orange",
                "very_conservative": "red",
            }
            color = confidence_colors.get(ev.confidence_tier, "gray")
            st.markdown(
                f"Confidence: :{color}[{ev.confidence_tier.replace('_', ' ').title()}]"
            )

            # Rare+ info
            st.caption(
                f"P(Rare+): {ev.p_rare_plus * 100:.2f}% | "
                f"P(Super Rare): {ev.p_super_rare * 100:.2f}% | "
                f"Conservative Score: {ev.conservative_score:.3f}"
            )
