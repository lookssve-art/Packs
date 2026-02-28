"""Custom CSS styles for the Streamlit dashboard."""

CUSTOM_CSS = """
<style>
    /* Main container */
    .main .block-container {
        padding-top: 1rem;
        max-width: 1400px;
    }

    /* Metric cards */
    [data-testid="stMetric"] {
        background-color: #1e1e2e;
        border: 1px solid #313244;
        border-radius: 8px;
        padding: 12px 16px;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.8rem;
    }
    [data-testid="stMetricDelta"] > div {
        font-size: 0.9rem;
    }

    /* Alert styling */
    .alert-critical {
        background-color: #f38ba8;
        color: #1e1e2e;
        padding: 8px 16px;
        border-radius: 6px;
        margin: 4px 0;
        font-weight: bold;
    }
    .alert-warning {
        background-color: #fab387;
        color: #1e1e2e;
        padding: 8px 16px;
        border-radius: 6px;
        margin: 4px 0;
    }
    .alert-info {
        background-color: #89b4fa;
        color: #1e1e2e;
        padding: 8px 16px;
        border-radius: 6px;
        margin: 4px 0;
    }

    /* Pack ranking cards */
    .ranking-card {
        background-color: #1e1e2e;
        border: 1px solid #313244;
        border-radius: 8px;
        padding: 16px;
        margin: 4px 0;
    }

    /* Confidence badges */
    .confidence-calibrated {
        background-color: #a6e3a1;
        color: #1e1e2e;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
    }
    .confidence-partial {
        background-color: #f9e2af;
        color: #1e1e2e;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
    }
    .confidence-very_conservative {
        background-color: #f38ba8;
        color: #1e1e2e;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
    }

    /* Model warning banner */
    .model-banner {
        padding: 10px 16px;
        border-radius: 6px;
        margin-bottom: 16px;
        font-size: 0.9rem;
    }
    .model-iid {
        background-color: #313244;
        border-left: 4px solid #89b4fa;
    }
    .model-pool {
        background-color: #313244;
        border-left: 4px solid #fab387;
    }

    /* Table styling */
    .dataframe {
        font-size: 0.85rem;
    }
</style>
"""
