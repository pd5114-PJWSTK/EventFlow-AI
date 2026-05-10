from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.services import ai_event_ingest_service as ingest_service


def _create_cp05_event(api_client: TestClient) -> str:
    client_response = api_client.post("/api/clients", json={"name": "CP05 Client"})
    assert client_response.status_code == 201
    location_response = api_client.post(
        "/api/locations",
        json={
            "name": "CP05 Venue",
            "city": "Gdansk",
            "location_type": "conference_center",
            "parking_difficulty": 2,
            "access_difficulty": 2,
            "setup_complexity_score": 4,
        },
    )
    assert location_response.status_code == 201
    start = datetime.now(UTC) + timedelta(days=14)
    event_response = api_client.post(
        "/api/events",
        json={
            "client_id": client_response.json()["client_id"],
            "location_id": location_response.json()["location_id"],
            "event_name": "CP05 Live Commit Event",
            "event_type": "conference",
            "planned_start": start.isoformat(),
            "planned_end": (start + timedelta(hours=8)).isoformat(),
            "priority": "medium",
            "status": "planned",
        },
    )
    assert event_response.status_code == 201
    return event_response.json()["event_id"]


def test_phase8_frontend_cp05_ingest_preview_prefers_structured_llm(monkeypatch, api_client: TestClient) -> None:
    def fake_llm_parser(_raw_input: str) -> ingest_service._LLMIntakePayload:
        return ingest_service._LLMIntakePayload(
            client_name="ACME Real Events",
            client_priority="high",
            location_name="Amber Expo",
            city="Gdansk",
            location_type="conference_center",
            setup_complexity_score=4,
            access_difficulty=2,
            parking_difficulty=2,
            event_name="Executive Product Launch",
            event_type="product_launch",
            event_subtype="enterprise",
            attendee_count=420,
            planned_start="2026-07-20T09:00:00+02:00",
            planned_end="2026-07-20T18:00:00+02:00",
            event_priority="high",
            budget_estimate="85000",
            requires_transport=True,
            requires_setup=True,
            requires_teardown=True,
            assumptions=["Parsed by the structured CP05 LLM intake path."],
            requirements=[
                ingest_service._LLMIntakeRequirement(requirement_type="person_role", role_required="coordinator", quantity=2),
                ingest_service._LLMIntakeRequirement(requirement_type="person_role", role_required="technician", quantity=1),
                ingest_service._LLMIntakeRequirement(requirement_type="equipment_type", equipment_type_name="LED screen", quantity=2),
                ingest_service._LLMIntakeRequirement(requirement_type="vehicle_type", vehicle_type_required="van", quantity=1),
            ],
        )

    monkeypatch.setattr(ingest_service, "_parse_event_intake_with_llm", fake_llm_parser)

    response = api_client.post(
        "/api/ai-agents/ingest-event/preview",
        json={"raw_input": "Plan the ACME launch from free text.", "prefer_langgraph": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["parser_mode"] == "llm"
    assert payload["used_fallback"] is False
    assert payload["draft"]["event_name"] == "Executive Product Launch"
    assert payload["draft"]["city"] == "Gdansk"
    assert len(payload["draft"]["requirements"]) == 4


def test_phase8_frontend_cp05_post_event_commit_does_not_500(api_client: TestClient) -> None:
    event_id = _create_cp05_event(api_client)

    parse_response = api_client.post(
        f"/api/runtime/events/{event_id}/post-event/parse",
        json={
            "raw_summary": "Event finished on time. Delay 0 minutes. Actual cost 51000 PLN. Client score 4.8 and internal score 4.6.",
            "prefer_llm": False,
            "idempotency_key": "cp05-post-parse",
        },
    )
    assert parse_response.status_code == 200

    commit_response = api_client.post(
        f"/api/runtime/events/{event_id}/post-event/commit",
        json={
            "completion": parse_response.json()["draft_complete"],
            "source_mode": "sheet_review",
            "idempotency_key": "cp05-post-commit",
        },
    )

    assert commit_response.status_code == 200
    assert commit_response.json()["completion"]["event_status"] == "completed"


def test_phase8_frontend_cp05_training_seed_contains_60_coherent_examples() -> None:
    patch = Path("scripts/sql/production_upgrade.sql").read_text(encoding="utf-8")

    assert "generate_series(1, 60)" in patch
    assert "TRAIN-001" in patch
    assert "TRAIN-060" in patch
    assert "'training_seed_cp05'" in patch
