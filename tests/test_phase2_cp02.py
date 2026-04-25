from __future__ import annotations

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
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_resource_crud_happy_path(api_client: TestClient) -> None:
    location = api_client.post("/api/locations", json={"name": "HQ", "city": "Warsaw"})
    assert location.status_code == 201
    location_id = location.json()["location_id"]

    skill = api_client.post(
        "/api/resources/skills",
        json={"skill_name": "audio_mixing", "skill_category": "audio"},
    )
    assert skill.status_code == 201
    skill_id = skill.json()["skill_id"]

    person = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "Jan Kowalski",
            "role": "technician_audio",
            "home_base_location_id": location_id,
            "cost_per_hour": 120,
        },
    )
    assert person.status_code == 201
    person_id = person.json()["person_id"]

    assign = api_client.post(
        f"/api/resources/people/{person_id}/skills",
        json={"skill_id": skill_id, "skill_level": 4, "certified": True},
    )
    assert assign.status_code == 200
    assert assign.json()["skill_level"] == 4

    eq_type = api_client.post(
        "/api/resources/equipment-types",
        json={"type_name": "audio_console", "category": "audio"},
    )
    assert eq_type.status_code == 201
    eq_type_id = eq_type.json()["equipment_type_id"]

    equipment = api_client.post(
        "/api/resources/equipment",
        json={
            "equipment_type_id": eq_type_id,
            "asset_tag": "AUD-100",
            "warehouse_location_id": location_id,
            "hourly_cost_estimate": 80,
        },
    )
    assert equipment.status_code == 201
    equipment_id = equipment.json()["equipment_id"]

    vehicle = api_client.post(
        "/api/resources/vehicles",
        json={
            "vehicle_name": "Van 1",
            "vehicle_type": "van",
            "home_location_id": location_id,
            "cost_per_km": 2.5,
        },
    )
    assert vehicle.status_code == 201
    vehicle_id = vehicle.json()["vehicle_id"]

    list_people = api_client.get("/api/resources/people")
    assert list_people.status_code == 200
    assert list_people.json()["total"] == 1

    list_equipment = api_client.get("/api/resources/equipment")
    assert list_equipment.status_code == 200
    assert list_equipment.json()["total"] == 1

    patch_vehicle = api_client.patch(f"/api/resources/vehicles/{vehicle_id}", json={"status": "maintenance"})
    assert patch_vehicle.status_code == 200
    assert patch_vehicle.json()["status"] == "maintenance"

    del_equipment = api_client.delete(f"/api/resources/equipment/{equipment_id}")
    assert del_equipment.status_code == 204


def test_resource_validation_missing_refs(api_client: TestClient) -> None:
    person_bad = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "No Base",
            "role": "driver",
            "home_base_location_id": "11111111-1111-1111-1111-111111111111",
        },
    )
    assert person_bad.status_code == 400

    equipment_bad = api_client.post(
        "/api/resources/equipment",
        json={
            "equipment_type_id": "22222222-2222-2222-2222-222222222222",
            "asset_tag": "MISSING-TYPE",
        },
    )
    assert equipment_bad.status_code == 400

    vehicle_bad = api_client.post(
        "/api/resources/vehicles",
        json={
            "vehicle_name": "No Base",
            "vehicle_type": "van",
            "home_location_id": "33333333-3333-3333-3333-333333333333",
        },
    )
    assert vehicle_bad.status_code == 400
