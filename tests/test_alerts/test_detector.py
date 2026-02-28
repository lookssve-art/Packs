"""Tests for alert detector."""

import pytest

from src.models.dataclasses import EVResult
from src.alerts.detector import AlertDetector


@pytest.fixture
def detector():
    return AlertDetector()


class TestAlertDetector:
    def test_ev_ratio_above_1(self, detector):
        ev = EVResult(
            pack_type="emerald",
            ev=280.0,
            ev_ratio=1.12,
            pack_cost=250.0,
            confidence_tier="calibrated",
            obs_count=50,
            rarity_posteriors={},
            calibrated_values={},
            model_mode="iid",
            p_rare_plus=0.10,
            p_super_rare=0.02,
            conservative_score=1.0,
        )
        alerts = detector.check_all([ev])
        ev_alerts = [a for a in alerts if a.alert_type == "ev_ratio_above_1"]
        assert len(ev_alerts) >= 1
        assert ev_alerts[0].severity == "warning"

    def test_ev_ratio_highly_above_1(self, detector):
        ev = EVResult(
            pack_type="emerald",
            ev=350.0,
            ev_ratio=1.40,
            pack_cost=250.0,
            confidence_tier="calibrated",
            obs_count=50,
            rarity_posteriors={},
            calibrated_values={},
            model_mode="iid",
            p_rare_plus=0.10,
            p_super_rare=0.02,
            conservative_score=1.2,
        )
        alerts = detector.check_all([ev])
        ev_alerts = [a for a in alerts if a.alert_type == "ev_ratio_above_1"]
        assert len(ev_alerts) >= 1
        assert ev_alerts[0].severity == "critical"

    def test_no_alert_below_threshold(self, detector):
        ev = EVResult(
            pack_type="sapphire",
            ev=40.0,
            ev_ratio=0.80,
            pack_cost=50.0,
            confidence_tier="calibrated",
            obs_count=50,
            rarity_posteriors={},
            calibrated_values={},
            model_mode="iid",
            p_rare_plus=0.05,
            p_super_rare=0.01,
            conservative_score=0.70,
        )
        alerts = detector.check_all([ev])
        ev_alerts = [a for a in alerts if a.alert_type == "ev_ratio_above_1"]
        assert len(ev_alerts) == 0

    def test_ev_ratio_increase_alert(self, detector):
        # First call — establishes baseline
        ev1 = EVResult(
            pack_type="sapphire", ev=40.0, ev_ratio=0.80,
            pack_cost=50.0, confidence_tier="calibrated", obs_count=50,
            rarity_posteriors={}, calibrated_values={}, model_mode="iid",
        )
        detector.check_all([ev1])

        # Second call — significant increase
        ev2 = EVResult(
            pack_type="sapphire", ev=55.0, ev_ratio=1.10,
            pack_cost=50.0, confidence_tier="calibrated", obs_count=55,
            rarity_posteriors={}, calibrated_values={}, model_mode="iid",
            conservative_score=0.95,
        )
        alerts = detector.check_all([ev2])
        increase_alerts = [a for a in alerts if a.alert_type == "ev_ratio_increase"]
        assert len(increase_alerts) >= 1
