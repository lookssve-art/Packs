"""Alert dispatcher — routes alerts to various outputs."""

from __future__ import annotations

import logging

from src.models.dataclasses import Alert

logger = logging.getLogger(__name__)


def dispatch_alert(alert: Alert) -> None:
    """Dispatch an alert to all configured outputs.

    Currently supports logging. Can be extended with:
    - Webhook (Discord, Telegram)
    - Email
    - Push notification
    """
    severity_map = {
        "info": logger.info,
        "warning": logger.warning,
        "critical": logger.critical,
    }

    log_fn = severity_map.get(alert.severity, logger.info)
    log_fn(
        "[ALERT] [%s] [%s] %s",
        alert.alert_type,
        alert.pack_type,
        alert.message,
    )
