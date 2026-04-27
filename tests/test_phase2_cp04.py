from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture
def api_client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {"core": None}},
        future=True,
    )
    testing_session_local = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, future=True
    )

    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def _future_window(hours: int = 4, days: int = 5) -> tuple[str, str]:
    start = datetime.now(timezone.utc) + timedelta(days=days)
    end = start + timedelta(hours=hours)
    return start.isoformat(), end.isoformat()


def create_event_context(
    api_client: TestClient,
    *,
    client_name: str,
    location_name: str,
    event_name: str,
    budget: Decimal,
    hours: int,
    days: int,
) -> tuple[str, str, str, str, str]:
    client_resp = api_client.post("/api/clients", json={"name": client_name})
    location_resp = api_client.post(
        "/api/locations", json={"name": location_name, "city": "Warsaw"}
    )
    assert client_resp.status_code == 201
    assert location_resp.status_code == 201

    client_id = client_resp.json()["client_id"]
    location_id = location_resp.json()["location_id"]
    planned_start, planned_end = _future_window(hours=hours, days=days)

    payload = {
        "client_id": client_id,
        "location_id": location_id,
        "event_name": event_name,
        "event_type": "conference",
        "planned_start": planned_start,
        "planned_end": planned_end,
        "budget_estimate": str(budget),
    }
    event_resp = api_client.post("/api/events", json=payload)
    assert event_resp.status_code == 201

    return (
        client_id,
        location_id,
        event_resp.json()["event_id"],
        planned_start,
        planned_end,
    )


def test_validate_constraints_supportable(api_client: TestClient) -> None:
    _, location_id, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Validation Client",
        location_name="Validation Venue",
        event_name="Validation Event",
        budget=Decimal("3000.00"),
        hours=4,
        days=5,
    )

    requirement_resp = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "person_role",
            "role_required": "coordinator",
            "quantity": 1,
        },
    )
    assert requirement_resp.status_code == 201

    person_resp = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "Lead Coordinator",
            "role": "coordinator",
            "home_base_location_id": location_id,
            "cost_per_hour": "120.00",
        },
    )
    assert person_resp.status_code == 201
    person_id = person_resp.json()["person_id"]

    availability_resp = api_client.post(
        f"/api/resources/people/{person_id}/availability",
        json={
            "available_from": planned_start,
            "available_to": planned_end,
            "is_available": True,
        },
    )
    assert availability_resp.status_code == 201

    validate_resp = api_client.post(
        "/api/planner/validate-constraints", json={"event_id": event_id}
    )
    assert validate_resp.status_code == 200
    payload = validate_resp.json()
    assert payload["is_supportable"] is True
    assert payload["gaps"] == []
    assert payload["budget_exceeded"] is False
    assert Decimal(payload["estimated_cost"]) > Decimal("0")


def test_validate_constraints_insufficient_quantity(api_client: TestClient) -> None:
    _, _, event_id, _, _ = create_event_context(
        api_client,
        client_name="Validation Client",
        location_name="Validation Venue",
        event_name="Validation Event",
        budget=Decimal("3000.00"),
        hours=4,
        days=5,
    )

    requirement_resp = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "person_role",
            "role_required": "coordinator",
            "quantity": 2,
        },
    )
    assert requirement_resp.status_code == 201

    validate_resp = api_client.post(
        "/api/planner/validate-constraints", json={"event_id": event_id}
    )
    assert validate_resp.status_code == 200
    payload = validate_resp.json()
    assert payload["is_supportable"] is False
    assert any(gap["code"] == "INSUFFICIENT_ROLE" for gap in payload["gaps"])


def test_validate_constraints_budget_exceeded(api_client: TestClient) -> None:
    _, location_id, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Validation Client",
        location_name="Validation Venue",
        event_name="Validation Event",
        budget=Decimal("200.00"),
        hours=4,
        days=5,
    )

    requirement_resp = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "person_role",
            "role_required": "coordinator",
            "quantity": 1,
        },
    )
    assert requirement_resp.status_code == 201

    person_resp = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "Expensive Coordinator",
            "role": "coordinator",
            "home_base_location_id": location_id,
            "cost_per_hour": "200.00",
        },
    )
    assert person_resp.status_code == 201
    person_id = person_resp.json()["person_id"]

    availability_resp = api_client.post(
        f"/api/resources/people/{person_id}/availability",
        json={
            "available_from": planned_start,
            "available_to": planned_end,
            "is_available": True,
        },
    )
    assert availability_resp.status_code == 201

    validate_resp = api_client.post(
        "/api/planner/validate-constraints", json={"event_id": event_id}
    )
    assert validate_resp.status_code == 200
    payload = validate_resp.json()
    assert payload["is_supportable"] is False
    assert payload["budget_exceeded"] is True
    assert any(gap["code"] == "BUDGET_EXCEEDED" for gap in payload["gaps"])


def test_validate_constraints_skill_mismatch(api_client: TestClient) -> None:
    _, location_id, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Validation Client",
        location_name="Validation Venue",
        event_name="Validation Event",
        budget=Decimal("3000.00"),
        hours=4,
        days=5,
    )

    skill_resp = api_client.post(
        "/api/resources/skills",
        json={"skill_name": "laser_safety", "skill_category": "safety"},
    )
    assert skill_resp.status_code == 201
    skill_id = skill_resp.json()["skill_id"]

    requirement_resp = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={"requirement_type": "person_skill", "skill_id": skill_id, "quantity": 1},
    )
    assert requirement_resp.status_code == 201

    person_resp = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "Generic Technician",
            "role": "technician_light",
            "home_base_location_id": location_id,
            "cost_per_hour": "80.00",
        },
    )
    assert person_resp.status_code == 201
    person_id = person_resp.json()["person_id"]

    availability_resp = api_client.post(
        f"/api/resources/people/{person_id}/availability",
        json={
            "available_from": planned_start,
            "available_to": planned_end,
            "is_available": True,
        },
    )
    assert availability_resp.status_code == 201

    validate_resp = api_client.post(
        "/api/planner/validate-constraints", json={"event_id": event_id}
    )
    assert validate_resp.status_code == 200
    payload = validate_resp.json()
    assert payload["is_supportable"] is False
    assert any(gap["code"] == "INSUFFICIENT_SKILL" for gap in payload["gaps"])


def test_validate_constraints_requirement_window_outside_event(
    api_client: TestClient,
) -> None:
    _, _, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Validation Client",
        location_name="Validation Venue",
        event_name="Validation Event",
        budget=Decimal("3000.00"),
        hours=4,
        days=5,
    )

    event_start = datetime.fromisoformat(planned_start)
    event_end = datetime.fromisoformat(planned_end)
    requirement_start = (event_start - timedelta(hours=2)).isoformat()
    requirement_end = (event_end - timedelta(hours=1)).isoformat()

    requirement_resp = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "person_role",
            "role_required": "coordinator",
            "quantity": 1,
            "required_start": requirement_start,
            "required_end": requirement_end,
        },
    )
    assert requirement_resp.status_code == 201

    validate_resp = api_client.post(
        "/api/planner/validate-constraints", json={"event_id": event_id}
    )
    assert validate_resp.status_code == 200
    payload = validate_resp.json()
    assert payload["is_supportable"] is False
    assert any(gap["code"] == "TIME_WINDOW_OUT_OF_EVENT" for gap in payload["gaps"])


def test_validate_constraints_missing_event(api_client: TestClient) -> None:
    validate_resp = api_client.post(
        "/api/planner/validate-constraints",
        json={"event_id": "11111111-1111-1111-1111-111111111111"},
    )
    assert validate_resp.status_code == 404
