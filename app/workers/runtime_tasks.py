from __future__ import annotations

from app.celery_app import celery_app


@celery_app.task(name="app.workers.runtime_tasks.send_runtime_notification")
def send_runtime_notification(
    *,
    event_id: str,
    notification_type: str,
    payload: dict | None = None,
) -> dict:
    return {
        "event_id": event_id,
        "notification_type": notification_type,
        "payload": payload or {},
    }
