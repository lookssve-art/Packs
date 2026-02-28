"""Alert condition detection engine."""

from __future__ import annotations

import datetime
from typing import Any

from config.settings import Settings
from src.models.dataclasses import Alert, EVResult


class AlertDetector:
    """Evaluates alert conditions against current EV data."""

    def __init__(self, settings: Settings | None = None):
        s = settings or Settings()
        self.ev_ratio_threshold = s.ev_ratio_alert_threshold
        self.ev_increase_threshold = s.ev_ratio_increase_threshold
        self.rare_plus_threshold = s.rare_plus_score_threshold
        self._last_ev: dict[str, float] = {}

    def check_all(
        self,
        ev_results: list[EVResult],
        published_rates: dict[str, dict[str, float]] | None = None,
    ) -> list[Alert]:
        """Check all alert conditions and return triggered alerts."""
        alerts: list[Alert] = []
        now = datetime.datetime.utcnow()

        for ev in ev_results:
            # 1. EV Ratio > 1.0 (positive expected value)
            if ev.ev_ratio >= self.ev_ratio_threshold:
                alerts.append(Alert(
                    timestamp=now,
                    alert_type="ev_ratio_above_1",
                    pack_type=ev.pack_type,
                    severity="critical" if ev.ev_ratio >= 1.2 else "warning",
                    message=(
                        f"{ev.pack_type.title()} Pack hat EV Ratio "
                        f"{ev.ev_ratio:.3f} (>1.0 = positiver Erwartungswert!)"
                    ),
                    details={
                        "ev_ratio": ev.ev_ratio,
                        "ev": ev.ev,
                        "pack_cost": ev.pack_cost,
                        "confidence": ev.confidence_tier,
                    },
                ))

            # 2. EV Ratio significant increase
            prev = self._last_ev.get(ev.pack_type, 0.0)
            if prev > 0:
                change = (ev.ev_ratio - prev) / prev
                if change >= self.ev_increase_threshold:
                    alerts.append(Alert(
                        timestamp=now,
                        alert_type="ev_ratio_increase",
                        pack_type=ev.pack_type,
                        severity="warning",
                        message=(
                            f"{ev.pack_type.title()} EV Ratio stieg um "
                            f"{change * 100:.1f}%: {prev:.3f} → {ev.ev_ratio:.3f}"
                        ),
                        details={
                            "old_ratio": prev,
                            "new_ratio": ev.ev_ratio,
                            "change_pct": change * 100,
                        },
                    ))

            # 3. Rare+ conservative score above threshold
            if ev.conservative_score >= self.rare_plus_threshold:
                alerts.append(Alert(
                    timestamp=now,
                    alert_type="rare_plus_above_threshold",
                    pack_type=ev.pack_type,
                    severity="info",
                    message=(
                        f"{ev.pack_type.title()} Rare+ konservativer Score: "
                        f"{ev.conservative_score:.3f} (Threshold: {self.rare_plus_threshold})"
                    ),
                    details={
                        "conservative_score": ev.conservative_score,
                        "p_rare_plus": ev.p_rare_plus,
                        "p_super_rare": ev.p_super_rare,
                    },
                ))

            # Update last known EV
            self._last_ev[ev.pack_type] = ev.ev_ratio

        return alerts
