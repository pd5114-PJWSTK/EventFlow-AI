from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import create_event_context, future_window


def test_generate_plan_commits_assignments_and_marks_event_planned(
    api_client: TestClient,
) -> None:
    _, location_id, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Phase4 CP03 Client",
        location_name="Phase4 CP03 Venue",
        event_name="Phase4 CP03 Event",
        hours=4,
        days=9,
    )

    requirement = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "person_role",
            "role_required": "coordinator",
            "quantity": 1,
        },
    )
    assert requirement.status_code == 201

    person = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "CP03 Coordinator",
            "role": "coordinator",
            "home_base_location_id": location_id,
            "cost_per_hour": "75.00",
        },
    )
    assert person.status_code == 201

    availability = api_client.post(
        f"/api/resources/people/{person.json()['person_id']}/availability",
        json={
            "available_from": planned_start,
            "available_to": planned_end,
            "is_available": True,
        },
    )
    assert availability.status_code == 201

    response = api_client.post(
        "/api/planner/generate-plan",
        json={"event_id": event_id, "initiated_by": "pytest"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["event_id"] == event_id
    assert payload["planner_run_id"]
    assert payload["recommendation_id"]
    assert payload["is_fully_assigned"] is True
    assert len(payload["assignment_ids"]) == 1
    assert payload["assignments"][0]["requirement_id"] == requirement.json()[
        "requirement_id"
    ]
    assert payload["assignments"][0]["resource_ids"] == [person.json()["person_id"]]
    assert payload["estimated_cost"] == "300.00"

    event_response = api_client.get(f"/api/events/{event_id}")
    assert event_response.status_code == 200
    assert event_response.json()["status"] == "planned"


def test_generate_plan_creates_vehicle_transport_leg(api_client: TestClient) -> None:
    client = api_client.post("/api/clients", json={"name": "Phase4 Transport Client"})
    home = api_client.post(
        "/api/locations",
        json={
            "name": "Warehouse",
            "city": "Warsaw",
            "latitude": "52.229700",
            "longitude": "21.012200",
        },
    )
    venue = api_client.post(
        "/api/locations",
        json={
            "name": "Venue",
            "city": "Lodz",
            "latitude": "51.759200",
            "longitude": "19.455000",
        },
    )
    assert client.status_code == 201
    assert home.status_code == 201
    assert venue.status_code == 201

    planned_start, planned_end = future_window(hours=3, days=10)
    event = api_client.post(
        "/api/events",
        json={
            "client_id": client.json()["client_id"],
            "location_id": venue.json()["location_id"],
            "event_name": "Phase4 Transport Event",
            "event_type": "conference",
            "planned_start": planned_start,
            "planned_end": planned_end,
        },
    )
    assert event.status_code == 201
    event_id = event.json()["event_id"]

    vehicle = api_client.post(
        "/api/resources/vehicles",
        json={
            "vehicle_name": "CP03 Truck",
            "vehicle_type": "truck",
            "home_location_id": home.json()["location_id"],
            "cost_per_hour": "120.00",
        },
    )
    assert vehicle.status_code == 201

    requirement = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "vehicle_type",
            "vehicle_type_required": "truck",
            "quantity": 1,
        },
    )
    assert requirement.status_code == 201

    availability = api_client.post(
        f"/api/resources/vehicles/{vehicle.json()['vehicle_id']}/availability",
        json={
            "available_from": planned_start,
            "available_to": planned_end,
            "is_available": True,
        },
    )
    assert availability.status_code == 201

    response = api_client.post("/api/planner/generate-plan", json={"event_id": event_id})

    assert response.status_code == 200
    payload = response.json()
    assert payload["is_fully_assigned"] is True
    assert len(payload["assignment_ids"]) == 1
    assert len(payload["transport_leg_ids"]) == 1
    assert payload["assignments"][0]["resource_type"] == "vehicle"
