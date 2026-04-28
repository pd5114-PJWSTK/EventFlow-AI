from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from app.services.planner_input_builder import build_planner_input


@dataclass(frozen=True)
class EventStub:
    planned_start: datetime
    planned_end: datetime


@dataclass(frozen=True)
class RequirementStub:
    requirement_id: str
    requirement_type: str
    quantity: Decimal
    mandatory: bool = True
    required_start: datetime | None = None
    required_end: datetime | None = None
    role_required: str | None = None
    skill_id: str | None = None
    equipment_type_id: str | None = None
    vehicle_type_required: str | None = None


@dataclass(frozen=True)
class PersonStub:
    person_id: str
    role: str
    availability_status: str
    max_daily_hours: Decimal
    cost_per_hour: Decimal
    reliability_notes: str | None
    active: bool = True


@dataclass(frozen=True)
class EquipmentStub:
    equipment_id: str
    equipment_type_id: str
    status: str
    hourly_cost_estimate: Decimal
    active: bool = True


@dataclass(frozen=True)
class VehicleStub:
    vehicle_id: str
    vehicle_type: str
    status: str
    cost_per_hour: Decimal
    cost_per_km: Decimal | None = None
    active: bool = True


@dataclass(frozen=True)
class AvailabilityStub:
    available_from: datetime
    available_to: datetime
    is_available: bool = True


def test_build_planner_input_filters_by_skill_and_availability() -> None:
    start = datetime(2030, 1, 1, 8, 0, 0)
    end = datetime(2030, 1, 1, 12, 0, 0)
    event = EventStub(planned_start=start, planned_end=end)

    requirement = RequirementStub(
        requirement_id="req-skill",
        requirement_type="person_skill",
        quantity=Decimal("1"),
        skill_id="skill-1",
    )

    people = [
        PersonStub(
            person_id="person-1",
            role="coordinator",
            availability_status="available",
            max_daily_hours=Decimal("8"),
            cost_per_hour=Decimal("100"),
            reliability_notes="high",
        ),
        PersonStub(
            person_id="person-2",
            role="coordinator",
            availability_status="available",
            max_daily_hours=Decimal("8"),
            cost_per_hour=Decimal("60"),
            reliability_notes="medium",
        ),
        PersonStub(
            person_id="person-3",
            role="coordinator",
            availability_status="available",
            max_daily_hours=Decimal("8"),
            cost_per_hour=Decimal("50"),
            reliability_notes=None,
        ),
    ]

    skills_by_person = {
        "person-1": {"skill-1"},
        "person-2": {"skill-1"},
    }

    people_availability = {
        "person-1": [AvailabilityStub(available_from=start, available_to=end)],
        "person-2": [
            AvailabilityStub(
                available_from=end + timedelta(hours=1),
                available_to=end + timedelta(hours=4),
            )
        ],
    }

    result = build_planner_input(
        event=event,
        requirements=[requirement],
        people=people,
        equipment=[],
        vehicles=[],
        people_availability=people_availability,
        equipment_availability={},
        vehicle_availability={},
        skills_by_person=skills_by_person,
    )

    assert len(result.requirements) == 1
    mapped = result.requirements[0]
    assert mapped.required_start == start
    assert mapped.required_end == end
    assert mapped.resource_type == "person"
    assert len(mapped.candidates) == 1
    assert mapped.candidates[0].resource_id == "person-1"
    assert mapped.candidates[0].available_from == start
    assert mapped.candidates[0].available_to == end

    expected_score = Decimal("1") / (Decimal("100") + Decimal("1")) + Decimal("0.20")
    assert mapped.candidates[0].score == expected_score


def test_build_planner_input_maps_equipment_and_vehicle_requirements() -> None:
    start = datetime(2030, 2, 1, 9, 0, 0)
    end = datetime(2030, 2, 1, 11, 0, 0)
    event = EventStub(planned_start=start, planned_end=end)

    requirements = [
        RequirementStub(
            requirement_id="req-eq",
            requirement_type="equipment_type",
            quantity=Decimal("1.25"),
            equipment_type_id="eq-type-1",
        ),
        RequirementStub(
            requirement_id="req-veh",
            requirement_type="vehicle_type",
            quantity=Decimal("2"),
            vehicle_type_required="truck",
        ),
    ]

    equipment = [
        EquipmentStub(
            equipment_id="eq-1",
            equipment_type_id="eq-type-1",
            status="available",
            hourly_cost_estimate=Decimal("30"),
        ),
        EquipmentStub(
            equipment_id="eq-2",
            equipment_type_id="eq-type-1",
            status="available",
            hourly_cost_estimate=Decimal("20"),
        ),
    ]
    vehicles = [
        VehicleStub(
            vehicle_id="veh-1",
            vehicle_type="truck",
            status="available",
            cost_per_hour=Decimal("50"),
        ),
        VehicleStub(
            vehicle_id="veh-2",
            vehicle_type="truck",
            status="available",
            cost_per_hour=Decimal("60"),
        ),
    ]

    equipment_availability = {
        "eq-1": [AvailabilityStub(available_from=start, available_to=end)],
        "eq-2": [AvailabilityStub(available_from=start, available_to=end)],
    }
    vehicle_availability = {
        "veh-1": [AvailabilityStub(available_from=start, available_to=end)],
        "veh-2": [AvailabilityStub(available_from=start, available_to=end)],
    }

    result = build_planner_input(
        event=event,
        requirements=requirements,
        people=[],
        equipment=equipment,
        vehicles=vehicles,
        people_availability={},
        equipment_availability=equipment_availability,
        vehicle_availability=vehicle_availability,
        skills_by_person={},
    )

    equipment_req = next(
        req for req in result.requirements if req.requirement_id == "req-eq"
    )
    vehicle_req = next(
        req for req in result.requirements if req.requirement_id == "req-veh"
    )

    assert equipment_req.quantity == 2
    assert equipment_req.resource_type == "equipment"
    assert equipment_req.candidates[0].resource_id == "eq-2"

    assert vehicle_req.quantity == 2
    assert vehicle_req.resource_type == "vehicle"
    assert vehicle_req.candidates[0].resource_id == "veh-1"
