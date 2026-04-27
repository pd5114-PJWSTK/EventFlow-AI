from __future__ import annotations

from fastapi.testclient import TestClient
from tests.helpers import create_event_context, future_window


def test_event_requirements_crud_and_validation(api_client: TestClient) -> None:
    _, location_id, event_id, _, _ = create_event_context(
        api_client,
        client_name="Req Client",
        location_name="Req Venue",
        event_name="Req Event",
        hours=5,
        days=3,
    )

    skill = api_client.post("/api/resources/skills", json={"skill_name": "rigging"})
    assert skill.status_code == 201
    skill_id = skill.json()["skill_id"]

    eq_type = api_client.post(
        "/api/resources/equipment-types", json={"type_name": "line_array"}
    )
    assert eq_type.status_code == 201
    eq_type_id = eq_type.json()["equipment_type_id"]

    req_role = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "person_role",
            "role_required": "coordinator",
            "quantity": 1,
        },
    )
    assert req_role.status_code == 201

    req_skill = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={"requirement_type": "person_skill", "skill_id": skill_id, "quantity": 2},
    )
    assert req_skill.status_code == 201

    req_eq = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={
            "requirement_type": "equipment_type",
            "equipment_type_id": eq_type_id,
            "quantity": 3,
        },
    )
    assert req_eq.status_code == 201

    bad_req = api_client.post(
        f"/api/events/{event_id}/requirements",
        json={"requirement_type": "person_skill", "quantity": 1},
    )
    assert bad_req.status_code == 422

    req_list = api_client.get(f"/api/events/{event_id}/requirements")
    assert req_list.status_code == 200
    assert req_list.json()["total"] == 3

    req_id = req_role.json()["requirement_id"]
    patched = api_client.patch(
        f"/api/events/{event_id}/requirements/{req_id}",
        json={"quantity": 2, "notes": "Need backup"},
    )
    assert patched.status_code == 200
    assert patched.json()["quantity"] == "2.00"

    deleted = api_client.delete(f"/api/events/{event_id}/requirements/{req_id}")
    assert deleted.status_code == 204


def test_availability_crud_and_conflict_detection(api_client: TestClient) -> None:
    _, location_id, _, _, _ = create_event_context(
        api_client,
        client_name="Req Client",
        location_name="Req Venue",
        event_name="Req Event",
        hours=5,
        days=3,
    )

    person = api_client.post(
        "/api/resources/people",
        json={
            "full_name": "Avail Person",
            "role": "driver",
            "home_base_location_id": location_id,
        },
    )
    assert person.status_code == 201
    person_id = person.json()["person_id"]

    eq_type = api_client.post(
        "/api/resources/equipment-types", json={"type_name": "mixer"}
    )
    assert eq_type.status_code == 201
    equipment = api_client.post(
        "/api/resources/equipment",
        json={
            "equipment_type_id": eq_type.json()["equipment_type_id"],
            "asset_tag": "EQ-AV-1",
        },
    )
    assert equipment.status_code == 201
    equipment_id = equipment.json()["equipment_id"]

    vehicle = api_client.post(
        "/api/resources/vehicles",
        json={
            "vehicle_name": "Truck A",
            "vehicle_type": "truck",
            "home_location_id": location_id,
        },
    )
    assert vehicle.status_code == 201
    vehicle_id = vehicle.json()["vehicle_id"]

    p_from, p_to = future_window(hours=3, days=3)
    p_win = api_client.post(
        f"/api/resources/people/{person_id}/availability",
        json={"available_from": p_from, "available_to": p_to, "is_available": True},
    )
    assert p_win.status_code == 201

    overlap = api_client.post(
        f"/api/resources/people/{person_id}/availability",
        json={"available_from": p_from, "available_to": p_to, "is_available": False},
    )
    assert overlap.status_code == 400

    p_list = api_client.get(f"/api/resources/people/{person_id}/availability")
    assert p_list.status_code == 200
    assert p_list.json()["total"] == 1

    e_from, e_to = future_window(hours=4, days=3)
    e_win = api_client.post(
        f"/api/resources/equipment/{equipment_id}/availability",
        json={"available_from": e_from, "available_to": e_to},
    )
    assert e_win.status_code == 201

    v_from, v_to = future_window(hours=2, days=3)
    v_win = api_client.post(
        f"/api/resources/vehicles/{vehicle_id}/availability",
        json={"available_from": v_from, "available_to": v_to},
    )
    assert v_win.status_code == 201

    updated = api_client.patch(
        f"/api/resources/vehicles/{vehicle_id}/availability/{v_win.json()['availability_id']}",
        json={"notes": "updated"},
    )
    assert updated.status_code == 200
    assert updated.json()["notes"] == "updated"

    deleted = api_client.delete(
        f"/api/resources/equipment/{equipment_id}/availability/{e_win.json()['availability_id']}"
    )
    assert deleted.status_code == 204
