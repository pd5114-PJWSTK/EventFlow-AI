from __future__ import annotations

from fastapi.testclient import TestClient
from tests.helpers import future_window


def test_clients_crud(api_client: TestClient) -> None:
    create_resp = api_client.post(
        "/api/clients",
        json={"name": "ACME", "industry": "events", "contact_email": "ops@acme.test"},
    )
    assert create_resp.status_code == 201
    client_id = create_resp.json()["client_id"]

    list_resp = api_client.get("/api/clients")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    patch_resp = api_client.patch(
        f"/api/clients/{client_id}", json={"name": "ACME Updated"}
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "ACME Updated"

    delete_resp = api_client.delete(f"/api/clients/{client_id}")
    assert delete_resp.status_code == 204

    get_resp = api_client.get(f"/api/clients/{client_id}")
    assert get_resp.status_code == 404


def test_locations_crud(api_client: TestClient) -> None:
    create_resp = api_client.post(
        "/api/locations",
        json={"name": "Expo Hall", "city": "Warsaw", "country_code": "PL"},
    )
    assert create_resp.status_code == 201
    location_id = create_resp.json()["location_id"]

    patch_resp = api_client.patch(
        f"/api/locations/{location_id}",
        json={"access_difficulty": 3, "setup_complexity_score": 7},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["access_difficulty"] == 3

    list_resp = api_client.get("/api/locations?limit=10&offset=0")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1


def test_events_crud_and_status_transitions(api_client: TestClient) -> None:
    client_resp = api_client.post("/api/clients", json={"name": "Client 1"})
    location_resp = api_client.post(
        "/api/locations", json={"name": "Main Venue", "city": "Gdansk"}
    )
    assert client_resp.status_code == 201
    assert location_resp.status_code == 201

    client_id = client_resp.json()["client_id"]
    location_id = location_resp.json()["location_id"]
    planned_start, planned_end = future_window(hours=4, days=1)

    create_event = api_client.post(
        "/api/events",
        json={
            "client_id": client_id,
            "location_id": location_id,
            "event_name": "Launch Event",
            "event_type": "conference",
            "planned_start": planned_start,
            "planned_end": planned_end,
        },
    )
    assert create_event.status_code == 201
    event_id = create_event.json()["event_id"]
    assert create_event.json()["status"] == "draft"

    submit_resp = api_client.patch(
        f"/api/events/{event_id}", json={"status": "submitted"}
    )
    assert submit_resp.status_code == 200
    assert submit_resp.json()["status"] == "submitted"

    invalid_transition = api_client.patch(
        f"/api/events/{event_id}", json={"status": "completed"}
    )
    assert invalid_transition.status_code == 400

    filtered = api_client.get("/api/events?status=submitted")
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1


def test_events_create_with_missing_refs_returns_400(api_client: TestClient) -> None:
    planned_start, planned_end = future_window(hours=4, days=1)
    response = api_client.post(
        "/api/events",
        json={
            "client_id": "11111111-1111-1111-1111-111111111111",
            "location_id": "22222222-2222-2222-2222-222222222222",
            "event_name": "Broken Event",
            "event_type": "concert",
            "planned_start": planned_start,
            "planned_end": planned_end,
        },
    )
    assert response.status_code == 400
