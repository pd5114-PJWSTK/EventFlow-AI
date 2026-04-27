from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient


def future_window(hours: int = 4, days: int = 1) -> tuple[str, str]:
    start = datetime.now(timezone.utc) + timedelta(days=days)
    end = start + timedelta(hours=hours)
    return start.isoformat(), end.isoformat()


def create_event_context(
    api_client: TestClient,
    *,
    client_name: str = "Test Client",
    location_name: str = "Test Venue",
    city: str = "Warsaw",
    event_name: str = "Test Event",
    event_type: str = "conference",
    budget: Decimal | None = None,
    hours: int = 4,
    days: int = 1,
) -> tuple[str, str, str, str, str]:
    client_resp = api_client.post("/api/clients", json={"name": client_name})
    location_resp = api_client.post(
        "/api/locations", json={"name": location_name, "city": city}
    )
    assert client_resp.status_code == 201
    assert location_resp.status_code == 201

    client_id = client_resp.json()["client_id"]
    location_id = location_resp.json()["location_id"]

    planned_start, planned_end = future_window(hours=hours, days=days)
    payload = {
        "client_id": client_id,
        "location_id": location_id,
        "event_name": event_name,
        "event_type": event_type,
        "planned_start": planned_start,
        "planned_end": planned_end,
    }
    if budget is not None:
        payload["budget_estimate"] = str(budget)

    event_resp = api_client.post("/api/events", json=payload)
    assert event_resp.status_code == 201

    return (
        client_id,
        location_id,
        event_resp.json()["event_id"],
        planned_start,
        planned_end,
    )
