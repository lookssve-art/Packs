"""GET /api/alerts — active and historical alerts."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_alert_repo

router = APIRouter(tags=["alerts"])


@router.get("/alerts/active")
def get_active_alerts(alert_repo=Depends(get_alert_repo)):
    alerts = alert_repo.get_active()
    return [
        {
            "id": a.id,
            "timestamp": a.timestamp.isoformat(),
            "alert_type": a.alert_type,
            "pack_type": a.pack_type,
            "severity": a.severity,
            "message": a.message,
            "details": a.details,
            "acknowledged": a.acknowledged,
        }
        for a in alerts
    ]


@router.get("/alerts/history")
def get_alert_history(
    limit: int = Query(default=100, le=500),
    alert_repo=Depends(get_alert_repo),
):
    alerts = alert_repo.get_recent(limit)
    return [
        {
            "id": a.id,
            "timestamp": a.timestamp.isoformat(),
            "alert_type": a.alert_type,
            "pack_type": a.pack_type,
            "severity": a.severity,
            "message": a.message,
            "acknowledged": a.acknowledged,
        }
        for a in alerts
    ]


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, alert_repo=Depends(get_alert_repo)):
    alert_repo.acknowledge(alert_id)
    return {"status": "ok"}
