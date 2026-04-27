from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from tests.helpers import create_event_context


def test_ranked_people_prefers_lower_cost(api_client: TestClient) -> None:
    _, location_id, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Phase3 CP03 Ranking Client",
        location_name="Phase3 CP03 Ranking Venue",
        event_name="Phase3 CP03 Ranking Event",
        budget=Decimal("2000.00"),
        hours=4,
        days=6,
    )

    req_resp = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "person_role",
            "role_required": "coordinator",
            "quantity": 1,
        },
    )
    assert req_resp.status_code == 201

    expensive = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "Expensive Coordinator",
            "role": "coordinator",
            "home_base_location_id": location_id,
            "cost_per_hour": "200.00",
            "reliability_notes": "medium",
        },
    )
    cheap = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "Cheap Coordinator",
            "role": "coordinator",
            "home_base_location_id": location_id,
            "cost_per_hour": "80.00",
            "reliability_notes": "medium",
        },
    )
    assert expensive.status_code == 201
    assert cheap.status_code == 201

    for person_id in [expensive.json()["person_id"], cheap.json()["person_id"]]:
        avail = api_client.post(
            f"/api/resources/people/{person_id}/availability",
            json={
                "available_from": planned_start,
                "available_to": planned_end,
                "is_available": True,
            },
        )
        assert avail.status_code == 201

    validate_resp = api_client.post(
        "/api/planner/validate-constraints", json={"event_id": event_id}
    )
    assert validate_resp.status_code == 200
    payload = validate_resp.json()

    assert payload["is_supportable"] is True
    # With ranking by lower cost, expected selected people cost = 80 * 4 = 320.
    assert Decimal(payload["cost_breakdown"]["people_cost"]) == Decimal("320.00")


def test_ranking_uses_reliability_notes_as_tie_breaker(api_client: TestClient) -> None:
    _, location_id, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Phase3 CP03 Reliability Client",
        location_name="Phase3 CP03 Reliability Venue",
        event_name="Phase3 CP03 Reliability Event",
        budget=Decimal("5000.00"),
        hours=4,
        days=6,
    )

    req_resp = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "person_role",
            "role_required": "coordinator",
            "quantity": 1,
        },
    )
    assert req_resp.status_code == 201

    high_reliability = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "High Reliability",
            "role": "coordinator",
            "home_base_location_id": location_id,
            "cost_per_hour": "100.00",
            "reliability_notes": "high reliability",
        },
    )
    normal_reliability = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "Normal Reliability",
            "role": "coordinator",
            "home_base_location_id": location_id,
            "cost_per_hour": "100.00",
            "reliability_notes": "medium reliability",
        },
    )
    assert high_reliability.status_code == 201
    assert normal_reliability.status_code == 201

    for person_id in [
        high_reliability.json()["person_id"],
        normal_reliability.json()["person_id"],
    ]:
        avail = api_client.post(
            f"/api/resources/people/{person_id}/availability",
            json={
                "available_from": planned_start,
                "available_to": planned_end,
                "is_available": True,
            },
        )
        assert avail.status_code == 201

    validate_resp = api_client.post(
        "/api/planner/validate-constraints", json={"event_id": event_id}
    )
    assert validate_resp.status_code == 200
    payload = validate_resp.json()

    assert payload["is_supportable"] is True
    # Same cost -> one selected by reliability boost, but final cost still 100 * 4.
    assert Decimal(payload["cost_breakdown"]["people_cost"]) == Decimal("400.00")


def test_optional_requirement_not_enough_ranked_resources_keeps_supportable(
    api_client: TestClient,
) -> None:
    _, location_id, event_id, planned_start, planned_end = create_event_context(
        api_client,
        client_name="Phase3 CP03 Optional Client",
        location_name="Phase3 CP03 Optional Venue",
        event_name="Phase3 CP03 Optional Event",
        budget=Decimal("3000.00"),
        hours=4,
        days=6,
    )

    req_resp = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "person_role",
            "role_required": "coordinator",
            "quantity": 2,
            "mandatory": False,
        },
    )
    assert req_resp.status_code == 201

    person = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "Only One Optional",
            "role": "coordinator",
            "home_base_location_id": location_id,
            "cost_per_hour": "90.00",
            "reliability_notes": "high",
        },
    )
    assert person.status_code == 201

    avail = api_client.post(
        f"/api/resources/people/{person.json()['person_id']}/availability",
        json={
            "available_from": planned_start,
            "available_to": planned_end,
            "is_available": True,
        },
    )
    assert avail.status_code == 201

    validate_resp = api_client.post(
        "/api/planner/validate-constraints", json={"event_id": event_id}
    )
    assert validate_resp.status_code == 200
    payload = validate_resp.json()

    assert payload["is_supportable"] is True
    assert any(gap["severity"] == "warning" for gap in payload["gaps"])
