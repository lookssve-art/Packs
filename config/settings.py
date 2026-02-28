"""Application settings loaded from environment variables."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    db_path: str = Field(default="data/packs.db")

    # Magic Eden API
    me_api_key: str | None = Field(default=None)
    me_base_url: str = "https://api-mainnet.magiceden.dev/v2"
    me_rate_limit_qps: float = 2.0
    me_rate_limit_qpm: int = 120
    me_rate_limit_burst: int = 5

    # Collection symbols to monitor
    collection_symbols: list[str] = Field(default=[
        "collector_crypt",
    ])

    # Collector
    poll_interval_seconds: int = 45
    discovery_cache_path: str = "data/discovered_endpoints.json"
    raw_data_dir: str = "data/raw"

    # Statistical model
    default_half_life_hours: float = 24.0
    prior_strength: float = 5.0
    confidence_threshold_partial: int = 3
    confidence_threshold_calibrated: int = 10
    conservative_haircut_very: float = 0.7
    conservative_haircut_partial: float = 0.85
    pool_mode_chi2_pvalue: float = 0.01

    # Alerts
    ev_ratio_alert_threshold: float = 1.0
    ev_ratio_increase_threshold: float = 0.10
    rare_plus_score_threshold: float = 0.15

    # Dashboard
    dashboard_refresh_ms: int = 15000
    dashboard_max_feed_items: int = 50

    # Rolling window
    max_pulls_window: int = 4000

    # Playwright
    playwright_headless: bool = True
    playwright_timeout_ms: int = 30000

    model_config = {"env_prefix": "PACKS_", "env_file": ".env"}
