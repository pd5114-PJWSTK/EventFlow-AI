from __future__ import annotations

from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import Any


_MAX_FEED_ITEMS = 200
_runtime_feed: dict[str, deque[dict[str, Any]]] = defaultdict(
    lambda: deque(maxlen=_MAX_FEED_ITEMS)
)


def publish_runtime_notification(
    *,
    event_id: str,
    notification_type: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item = {
        "event_id": event_id,
        "notification_type": notification_type,
        "payload": payload or {},
        "emitted_at": datetime.now(UTC).isoformat(),
    }
    _runtime_feed[event_id].append(item)
    return item


def list_runtime_notifications(event_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
    items = list(_runtime_feed.get(event_id, deque()))
    if limit <= 0:
        return []
    return items[-limit:]


def enqueue_runtime_notification(
    *,
    event_id: str,
    notification_type: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    publish_runtime_notification(
        event_id=event_id,
        notification_type=notification_type,
        payload=payload or {},
    )
    try:
        from app.workers.runtime_tasks import send_runtime_notification

        task = send_runtime_notification.delay(
            event_id=event_id,
            notification_type=notification_type,
            payload=payload or {},
        )
        return {
            "dispatch_mode": "local+celery",
            "task_id": getattr(task, "id", None),
        }
    except Exception:
        return {"dispatch_mode": "local_only", "task_id": None}
