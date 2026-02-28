"""Calibrated bucket value table component."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config.constants import RARITY_ORDER
from src.models.dataclasses import EVResult


def render_value_table(ev_results: list[EVResult]) -> None:
    """Render table of calibrated average values per rarity per pack."""
    st.subheader("Calibrated Value per Rarity")

    if not ev_results:
        st.info("Not enough data for value calibration.")
        return

    rows = []
    for ev in ev_results:
        for rarity in RARITY_ORDER:
            if rarity in ev.calibrated_values:
                mean, lower, upper = ev.rarity_posteriors.get(
                    rarity, (0.0, 0.0, 0.0)
                )
                rows.append({
                    "Pack": ev.pack_type.title(),
                    "Rarity": rarity.title(),
                    "Avg Value": f"${ev.calibrated_values[rarity]:.0f}",
                    "P(Rarity)": f"{mean * 100:.2f}%",
                    "CI 90%": f"{lower * 100:.2f}%–{upper * 100:.2f}%",
                    "Contribution to EV": f"${mean * ev.calibrated_values[rarity]:.2f}",
                    "Confidence": ev.confidence_tier.replace("_", " ").title(),
                })

    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No calibrated values available yet.")
