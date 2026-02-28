"""Streamlit dashboard — Magic Eden Pack EV Tracker.

Real-time dashboard showing live pull data, EV calculations,
odds comparisons, and pack rankings.

Run with: streamlit run src/dashboard/app.py
"""

from __future__ import annotations

import datetime
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from config.settings import Settings
from src.dashboard.components.alert_panel import render_alert_panel
from src.dashboard.components.ev_display import render_ev_metrics
from src.dashboard.components.live_feed import render_live_feed
from src.dashboard.components.model_status import render_model_status
from src.dashboard.components.odds_comparison import render_odds_comparison
from src.dashboard.components.odds_shift import render_odds_shift
from src.dashboard.components.pack_rankings import render_pack_rankings
from src.dashboard.components.trend_charts import render_ev_trend
from src.dashboard.components.value_table import render_value_table
from src.dashboard.styles import CUSTOM_CSS
from src.models.dataclasses import DropRateSnapshot, PackTypeInfo
from src.models.ev_calculator import compute_all_evs
from src.storage.database import get_connection, init_db
from src.storage.repositories import (
    AlertRepository,
    EVSnapshotRepository,
    PackTypeRepository,
    PullRepository,
    SnapshotRepository,
)


def main():
    st.set_page_config(
        page_title="Packs EV Tracker — Magic Eden",
        page_icon="🎴",
        layout="wide",
    )
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    settings = Settings()

    # Auto-refresh
    st_autorefresh(
        interval=settings.dashboard_refresh_ms,
        key="data_refresh",
    )

    # Database connection
    conn = get_connection(settings.db_path)
    init_db(conn)

    pull_repo = PullRepository(conn)
    snapshot_repo = SnapshotRepository(conn)
    ev_repo = EVSnapshotRepository(conn)
    alert_repo = AlertRepository(conn)
    pack_type_repo = PackTypeRepository(conn)

    # Sidebar controls
    with st.sidebar:
        st.title("Packs EV Tracker")
        st.caption("Magic Eden Pokemon Pack Analysis")

        # Get available pack types
        pack_types = pack_type_repo.get_all_active()
        pack_slugs = [p.slug for p in pack_types] if pack_types else ["sapphire", "emerald"]

        pack_filter = st.radio(
            "Pack Type",
            ["All"] + [s.title() for s in pack_slugs],
            index=0,
        )

        time_options = {"24h": 24, "7d": 168, "30d": 720, "All": 0}
        time_window = st.selectbox("Time Window", list(time_options.keys()), index=0)
        time_hours = time_options[time_window]

        model_mode = st.radio("Model Mode", ["IID", "Pool", "Auto"], index=0)

        half_life = st.slider(
            "Half-life (hours)",
            min_value=1,
            max_value=168,
            value=int(settings.default_half_life_hours),
        )

        st.divider()
        st.caption(f"Refresh: {settings.dashboard_refresh_ms / 1000:.0f}s")
        st.caption(f"DB: {settings.db_path}")

        # Stats
        pull_counts = pull_repo.get_count_by_pack()
        if pull_counts:
            st.divider()
            st.markdown("**Pull Counts**")
            for pack, count in pull_counts.items():
                st.text(f"  {pack}: {count}")

    # Filter parameters
    selected_pack = None if pack_filter == "All" else pack_filter.lower()
    since = None
    if time_hours > 0:
        since = datetime.datetime.utcnow() - datetime.timedelta(hours=time_hours)

    # Load data
    pulls = pull_repo.get_recent(
        pack_type=selected_pack,
        limit=settings.max_pulls_window,
        since=since,
    )

    # Get pack type info for EV calculation
    if not pack_types:
        # Use defaults
        from config.constants import KNOWN_PACKS
        pack_types = [
            PackTypeInfo(
                slug=slug,
                display_name=slug.title(),
                cost_usd=info["cost"],
                sellback_rate=info.get("sellback_rate"),
            )
            for slug, info in KNOWN_PACKS.items()
        ]

    # Filter pack types based on selection
    if selected_pack:
        pack_types = [p for p in pack_types if p.slug == selected_pack]

    # Get published rates
    published_snapshots: dict[str, DropRateSnapshot] = {}
    published_rates: dict[str, dict[str, float]] = {}
    for pack in pack_types:
        snapshot = snapshot_repo.get_latest(pack.slug)
        if snapshot:
            published_snapshots[pack.slug] = snapshot
            published_rates[pack.slug] = snapshot.rates

    # Compute EVs
    ev_results = compute_all_evs(
        all_pulls=pulls,
        pack_types=pack_types,
        published_rates=published_rates if published_rates else None,
        half_life_hours=float(half_life),
        prior_strength=settings.prior_strength,
    )

    # Main content
    st.title("Magic Eden Pack EV Tracker")

    # Model status banner
    render_model_status(model_mode.lower())

    # Tabs
    tab_overview, tab_analysis, tab_alerts = st.tabs([
        "Overview", "Deep Analysis", "Alerts"
    ])

    with tab_overview:
        # EV Metrics
        render_ev_metrics(ev_results)

        st.divider()

        # Pack Rankings
        render_pack_rankings(ev_results)

        st.divider()

        # Live Feed
        render_live_feed(pulls, max_items=settings.dashboard_max_feed_items)

    with tab_analysis:
        # Odds Comparison
        render_odds_comparison(ev_results, published_snapshots)

        st.divider()

        # Odds Shift Timeline
        snapshots_by_pack: dict[str, list[DropRateSnapshot]] = {}
        for pack in pack_types:
            history = snapshot_repo.get_history(pack.slug, limit=50)
            if history:
                snapshots_by_pack[pack.slug] = history
        render_odds_shift(snapshots_by_pack)

        st.divider()

        # Value Table
        render_value_table(ev_results)

        st.divider()

        # EV Trend
        ev_history: dict[str, list[dict]] = {}
        for pack in pack_types:
            history = ev_repo.get_history(pack.slug, limit=200)
            if history:
                ev_history[pack.slug] = history
        render_ev_trend(ev_history)

    with tab_alerts:
        active_alerts = alert_repo.get_active()
        recent_alerts = alert_repo.get_recent(limit=100)
        render_alert_panel(active_alerts, recent_alerts)

    conn.close()


if __name__ == "__main__":
    main()
