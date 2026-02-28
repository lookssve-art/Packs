"""Alert panel component — displays active and historical alerts."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.models.dataclasses import Alert


def render_alert_panel(
    active_alerts: list[Alert],
    recent_alerts: list[Alert],
) -> None:
    """Render alert panel with active and historical alerts."""

    # Active alerts
    st.subheader("Active Alerts")
    if not active_alerts:
        st.success("No active alerts.")
    else:
        for alert in active_alerts:
            _render_alert(alert)

    # Alert history
    st.subheader("Alert History")
    if not recent_alerts:
        st.info("No alerts recorded yet.")
        return

    rows = []
    for a in recent_alerts:
        rows.append({
            "Time": a.timestamp.strftime("%Y-%m-%d %H:%M"),
            "Type": a.alert_type.replace("_", " ").title(),
            "Pack": a.pack_type.title(),
            "Severity": a.severity.title(),
            "Message": a.message,
            "Ack": "Yes" if a.acknowledged else "No",
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_alert(alert: Alert) -> None:
    """Render a single alert with appropriate styling."""
    css_class = f"alert-{alert.severity}"
    st.markdown(
        f'<div class="{css_class}">'
        f'<strong>[{alert.severity.upper()}]</strong> '
        f'{alert.message}'
        f'</div>',
        unsafe_allow_html=True,
    )
