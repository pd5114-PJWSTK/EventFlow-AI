from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient


def _create_event(api_client: TestClient) -> str:
    client_response = api_client.post("/api/clients", json={"name": "CP04 FE Client"})
    assert client_response.status_code == 201
    location_response = api_client.post(
        "/api/locations",
        json={
            "name": "CP04 FE Venue",
            "city": "Warszawa",
            "location_type": "conference_center",
            "parking_difficulty": 2,
            "access_difficulty": 2,
            "setup_complexity_score": 4,
        },
    )
    assert location_response.status_code == 201
    start = datetime.now(UTC) + timedelta(days=7)
    end = start + timedelta(hours=5)
    event_response = api_client.post(
        "/api/events",
        json={
            "client_id": client_response.json()["client_id"],
            "location_id": location_response.json()["location_id"],
            "event_name": "CP04 FE Smoke Event",
            "event_type": "conference",
            "planned_start": start.isoformat(),
            "planned_end": end.isoformat(),
            "priority": "medium",
        },
    )
    assert event_response.status_code == 201
    return event_response.json()["event_id"]


def test_phase8_frontend_cp04_llm_status_reports_fallback(api_client: TestClient) -> None:
    response = api_client.get("/api/ai-agents/llm-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] in {"llm", "fallback"}
    assert "enabled" in payload
    assert "configured" in payload
    assert payload["message"]


def test_phase8_frontend_cp04_location_city_rejects_numeric_value(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/locations",
        json={
            "name": "Niepoprawna lokalizacja",
            "city": "12345",
            "location_type": "conference_center",
            "parking_difficulty": 2,
            "access_difficulty": 2,
            "setup_complexity_score": 4,
        },
    )

    assert response.status_code == 422


def test_phase8_frontend_cp04_post_event_parse_uses_idempotency(api_client: TestClient) -> None:
    event_id = _create_event(api_client)
    payload = {
        "raw_summary": "Event zakończony. Opóźnienie 15 minut. Koszt 47000 PLN.",
        "prefer_llm": True,
        "idempotency_key": "cp04-post-event-parse-idempotency",
    }

    first = api_client.post(f"/api/runtime/events/{event_id}/post-event/parse", json=payload)
    assert first.status_code == 200
    assert first.json()["draft_complete"]["total_delay_minutes"] == 15

    replay = api_client.post(f"/api/runtime/events/{event_id}/post-event/parse", json=payload)
    assert replay.status_code == 200
    assert replay.headers.get("X-Idempotency-Replayed") == "true"


def test_phase8_frontend_cp04_sql_patches_create_idempotency_records() -> None:
    schema = Path("docker/postgres/init/01_schema.sql").read_text(encoding="utf-8")
    patch = Path("scripts/sql/production_upgrade.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE ops.idempotency_records" in schema
    assert "CREATE TABLE IF NOT EXISTS ops.idempotency_records" in patch
    assert "uq_idempotency_scope_key" in schema
    assert "uq_idempotency_scope_key" in patch
