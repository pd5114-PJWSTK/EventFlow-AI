from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_CEILING
from typing import Iterable, Mapping, Sequence, TYPE_CHECKING

from app.services.ortools_service import (
    PlannerCandidate,
    PlannerInput,
    PlannerRequirement,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class PlannerInputError(ValueError):
    pass


def build_planner_input(
    *,
    event,
    requirements: Sequence,
    people: Sequence,
    equipment: Sequence,
    vehicles: Sequence,
    people_availability: Mapping[str, Sequence],
    equipment_availability: Mapping[str, Sequence],
    vehicle_availability: Mapping[str, Sequence],
    skills_by_person: Mapping[str, set[str]],
) -> PlannerInput:
    """Build a planner input payload without importing ORM models."""
    planner_requirements: list[PlannerRequirement] = []

    for requirement in requirements:
        req_start, req_end = _required_window(event, requirement)
        req_hours = _window_hours(req_start, req_end)
        quantity = _required_quantity(requirement)
        req_type = _enum_value(getattr(requirement, "requirement_type", None))

        if req_type in ("person_role", "person_skill"):
            candidates = _people_candidates(
                requirement=requirement,
                people=people,
                availability_map=people_availability,
                skills_by_person=skills_by_person,
                required_start=req_start,
                required_end=req_end,
                required_hours=req_hours,
            )
            resource_type = "person"
        elif req_type == "equipment_type":
            candidates = _equipment_candidates(
                requirement=requirement,
                equipment=equipment,
                availability_map=equipment_availability,
                required_start=req_start,
                required_end=req_end,
            )
            resource_type = "equipment"
        elif req_type == "vehicle_type":
            candidates = _vehicle_candidates(
                requirement=requirement,
                vehicles=vehicles,
                availability_map=vehicle_availability,
                required_start=req_start,
                required_end=req_end,
            )
            resource_type = "vehicle"
        else:
            candidates = []
            resource_type = "unknown"

        planner_requirements.append(
            PlannerRequirement(
                requirement_id=requirement.requirement_id,
                resource_type=resource_type,
                quantity=quantity,
                mandatory=getattr(requirement, "mandatory", True),
                required_start=req_start,
                required_end=req_end,
                candidates=candidates,
            )
        )

    return PlannerInput(requirements=planner_requirements)


def load_planner_input(db: Session, event_id: str) -> PlannerInput:
    from sqlalchemy import select

    from app.models.core import (
        Equipment,
        EquipmentAvailability,
        Event,
        EventRequirement,
        PeopleAvailability,
        PersonSkill,
        ResourcePerson,
        Vehicle,
        VehicleAvailability,
    )

    event = db.get(Event, event_id)
    if event is None:
        raise PlannerInputError("Event not found")

    requirements = (
        db.execute(
            select(EventRequirement).where(EventRequirement.event_id == event_id)
        )
        .scalars()
        .all()
    )
    people = (
        db.execute(select(ResourcePerson).where(ResourcePerson.active.is_(True)))
        .scalars()
        .all()
    )
    equipment = (
        db.execute(select(Equipment).where(Equipment.active.is_(True))).scalars().all()
    )
    vehicles = (
        db.execute(select(Vehicle).where(Vehicle.active.is_(True))).scalars().all()
    )

    skills_by_person: dict[str, set[str]] = {}
    for link in db.execute(select(PersonSkill)).scalars().all():
        skills_by_person.setdefault(link.person_id, set()).add(link.skill_id)

    people_availability = _availability_map(
        db.execute(
            select(PeopleAvailability).where(PeopleAvailability.is_available.is_(True))
        )
        .scalars()
        .all(),
        "person_id",
    )
    equipment_availability = _availability_map(
        db.execute(
            select(EquipmentAvailability).where(
                EquipmentAvailability.is_available.is_(True)
            )
        )
        .scalars()
        .all(),
        "equipment_id",
    )
    vehicle_availability = _availability_map(
        db.execute(
            select(VehicleAvailability).where(
                VehicleAvailability.is_available.is_(True)
            )
        )
        .scalars()
        .all(),
        "vehicle_id",
    )

    return build_planner_input(
        event=event,
        requirements=requirements,
        people=people,
        equipment=equipment,
        vehicles=vehicles,
        people_availability=people_availability,
        equipment_availability=equipment_availability,
        vehicle_availability=vehicle_availability,
        skills_by_person=skills_by_person,
    )


def _required_window(event, requirement) -> tuple[datetime, datetime]:
    start = getattr(requirement, "required_start", None) or event.planned_start
    end = getattr(requirement, "required_end", None) or event.planned_end
    return start, end


def _required_quantity(requirement) -> int:
    quantity = getattr(requirement, "quantity", 1)
    if isinstance(quantity, Decimal):
        return int(quantity.to_integral_value(rounding=ROUND_CEILING))
    return int(quantity)


def _window_hours(start: datetime, end: datetime) -> Decimal:
    seconds = (end - start).total_seconds()
    return Decimal(str(max(seconds, 0) / 3600.0))


def _people_candidates(
    *,
    requirement,
    people: Sequence,
    availability_map: Mapping[str, Sequence],
    skills_by_person: Mapping[str, set[str]],
    required_start: datetime,
    required_end: datetime,
    required_hours: Decimal,
) -> list[PlannerCandidate]:
    role_required = _enum_value(getattr(requirement, "role_required", None))
    skill_id = getattr(requirement, "skill_id", None)

    candidates: list[PlannerCandidate] = []
    for person in people:
        if not getattr(person, "active", True):
            continue
        if not _status_is_available(getattr(person, "availability_status", None)):
            continue
        if (
            role_required
            and _enum_value(getattr(person, "role", None)) != role_required
        ):
            continue
        if skill_id and skill_id not in skills_by_person.get(person.person_id, set()):
            continue
        if not _person_hours_eligible(person, required_hours):
            continue

        window = _find_covering_window(
            availability_map.get(person.person_id, ()), required_start, required_end
        )
        if window is None:
            continue

        cost = _decimal_or_zero(getattr(person, "cost_per_hour", None))
        score = _score_from_cost(cost) + _reliability_bonus(
            getattr(person, "reliability_notes", None)
        )
        candidates.append(
            PlannerCandidate(
                resource_id=person.person_id,
                cost_per_hour=cost,
                score=score,
                available_from=window.available_from,
                available_to=window.available_to,
            )
        )

    return _sorted_candidates(candidates)


def _equipment_candidates(
    *,
    requirement,
    equipment: Sequence,
    availability_map: Mapping[str, Sequence],
    required_start: datetime,
    required_end: datetime,
) -> list[PlannerCandidate]:
    equipment_type_id = getattr(requirement, "equipment_type_id", None)

    candidates: list[PlannerCandidate] = []
    for item in equipment:
        if not getattr(item, "active", True):
            continue
        if not _status_is_available(getattr(item, "status", None)):
            continue
        if equipment_type_id and item.equipment_type_id != equipment_type_id:
            continue

        window = _find_covering_window(
            availability_map.get(item.equipment_id, ()), required_start, required_end
        )
        if window is None:
            continue

        cost = _decimal_or_zero(getattr(item, "hourly_cost_estimate", None))
        candidates.append(
            PlannerCandidate(
                resource_id=item.equipment_id,
                cost_per_hour=cost,
                score=_score_from_cost(cost),
                available_from=window.available_from,
                available_to=window.available_to,
            )
        )

    return _sorted_candidates(candidates)


def _vehicle_candidates(
    *,
    requirement,
    vehicles: Sequence,
    availability_map: Mapping[str, Sequence],
    required_start: datetime,
    required_end: datetime,
) -> list[PlannerCandidate]:
    vehicle_type_required = _enum_value(
        getattr(requirement, "vehicle_type_required", None)
    )

    candidates: list[PlannerCandidate] = []
    for vehicle in vehicles:
        if not getattr(vehicle, "active", True):
            continue
        if not _status_is_available(getattr(vehicle, "status", None)):
            continue
        if (
            vehicle_type_required
            and _enum_value(getattr(vehicle, "vehicle_type", None))
            != vehicle_type_required
        ):
            continue

        window = _find_covering_window(
            availability_map.get(vehicle.vehicle_id, ()),
            required_start,
            required_end,
        )
        if window is None:
            continue

        cost = _decimal_or_zero(getattr(vehicle, "cost_per_hour", None))
        if cost == Decimal("0"):
            cost = _decimal_or_zero(getattr(vehicle, "cost_per_km", None))
        candidates.append(
            PlannerCandidate(
                resource_id=vehicle.vehicle_id,
                cost_per_hour=cost,
                score=_score_from_cost(cost),
                available_from=window.available_from,
                available_to=window.available_to,
            )
        )

    return _sorted_candidates(candidates)


def _availability_map(items: Iterable, key_attr: str) -> dict[str, list]:
    grouped: dict[str, list] = {}
    for item in items:
        grouped.setdefault(getattr(item, key_attr), []).append(item)
    for windows in grouped.values():
        windows.sort(key=lambda window: window.available_from)
    return grouped


def _find_covering_window(
    windows: Sequence, required_start: datetime, required_end: datetime
):
    for window in windows:
        if not getattr(window, "is_available", True):
            continue
        if (
            window.available_from <= required_start
            and window.available_to >= required_end
        ):
            return window
    return None


def _sorted_candidates(candidates: list[PlannerCandidate]) -> list[PlannerCandidate]:
    return sorted(
        candidates,
        key=lambda candidate: (
            -candidate.score,
            candidate.cost_per_hour,
            candidate.resource_id,
        ),
    )


def _score_from_cost(cost: Decimal) -> Decimal:
    return Decimal("1") / (cost + Decimal("1"))


def _reliability_bonus(notes: str | None) -> Decimal:
    if not notes:
        return Decimal("0")
    lowered = notes.lower()
    if "high" in lowered:
        return Decimal("0.20")
    if "medium" in lowered:
        return Decimal("0.10")
    return Decimal("0")


def _person_hours_eligible(person, required_hours: Decimal) -> bool:
    max_hours = getattr(person, "max_daily_hours", None)
    if max_hours is None:
        return True
    return max_hours >= required_hours


def _status_is_available(status) -> bool:
    value = _enum_value(status)
    return value in ("available", "reserved")


def _enum_value(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "value"):
        return value.value
    return str(value)


def _decimal_or_zero(value) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))
