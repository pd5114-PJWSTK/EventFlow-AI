from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient


def _create_client_location_event(api_client: TestClient) -> tuple[str, str, str]:
    client_resp = api_client.post("/api/clients", json={"name": "CP01 FE Client"})
    assert client_resp.status_code == 201
    client_id = client_resp.json()["client_id"]

    location_resp = api_client.post(
        "/api/locations",
        json={
            "name": "CP01 FE Venue",
            "city": "Warsaw",
            "location_type": "conference_center",
            "setup_complexity_score": 5,
            "access_difficulty": 3,
            "parking_difficulty": 2,
        },
    )
    assert location_resp.status_code == 201
    location_id = location_resp.json()["location_id"]

    start = datetime.now(UTC) + timedelta(days=1)
    end = start + timedelta(hours=8)
    event_resp = api_client.post(
        "/api/events",
        json={
            "client_id": client_id,
            "location_id": location_id,
            "event_name": "CP01 FE Event",
            "event_type": "conference",
            "planned_start": start.isoformat(),
            "planned_end": end.isoformat(),
            "priority": "medium",
        },
    )
    assert event_resp.status_code == 201
    return client_id, location_id, event_resp.json()["event_id"]


def test_phase8_frontend_cp01_ai_ingest_preview_and_commit(api_client: TestClient) -> None:
    preview = api_client.post(
        "/api/ai-agents/ingest-event/preview",
        json={
            "raw_input": """
            event_name: Event AI Preview
            city: Krakow
            requirement_person_coordinator: 2
            requirement_vehicle_van: 1
            """,
            "prefer_langgraph": False,
        },
    )
    assert preview.status_code == 200
    preview_payload = preview.json()
    assert "draft" in preview_payload
    assert isinstance(preview_payload.get("gaps", []), list)
    assert preview_payload["draft"]["event_name"] == "Event AI Preview"

    commit = api_client.post(
        "/api/ai-agents/ingest-event/commit",
        json={
            "draft": preview_payload["draft"],
            "assumptions": preview_payload.get("assumptions", []),
            "parser_mode": preview_payload.get("parser_mode", "manual_commit"),
            "used_fallback": preview_payload.get("used_fallback", False),
        },
    )
    assert commit.status_code == 200
    commit_payload = commit.json()
    assert commit_payload["event_id"]
    assert commit_payload["client_id"]
    assert commit_payload["location_id"]

    event_read = api_client.get(f"/api/events/{commit_payload['event_id']}")
    assert event_read.status_code == 200
    assert event_read.json()["event_name"] == "Event AI Preview"


def test_phase8_frontend_cp01_post_event_parse_and_commit(api_client: TestClient) -> None:
    _, _, event_id = _create_client_location_event(api_client)

    parse = api_client.post(
        f"/api/runtime/events/{event_id}/post-event/parse",
        json={
            "raw_summary": "Event finished on time. delay 0 minutes. cost 24500 PLN. quality high.",
            "prefer_llm": False,
            "idempotency_key": "post-event-parse-001",
        },
    )
    assert parse.status_code == 200
    parse_payload = parse.json()
    assert parse_payload["event_id"] == event_id
    assert parse_payload["draft_complete"]["summary_notes"]

    commit = api_client.post(
        f"/api/runtime/events/{event_id}/post-event/commit",
        json={
            "completion": parse_payload["draft_complete"],
            "source_mode": "sheet_review",
            "idempotency_key": "post-event-commit-001",
        },
    )
    assert commit.status_code == 200
    commit_payload = commit.json()
    assert commit_payload["event_id"] == event_id
    assert commit_payload["completion"]["event_status"] == "completed"

    event_read = api_client.get(f"/api/events/{event_id}")
    assert event_read.status_code == 200
    assert event_read.json()["status"] == "completed"

    replay = api_client.post(
        f"/api/runtime/events/{event_id}/post-event/commit",
        json={
            "completion": parse_payload["draft_complete"],
            "source_mode": "sheet_review",
            "idempotency_key": "post-event-commit-001",
        },
    )
    assert replay.status_code == 200
    assert replay.headers.get("X-Idempotency-Replayed") == "true"