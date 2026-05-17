from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_CEILING
from math import asin, cos, radians, sin, sqrt
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


_LOCKING_EVENT_STATUSES = {"planned", "confirmed", "in_progress"}
_LOCKING_ASSIGNMENT_STATUSES = {"proposed", "planned", "confirmed", "active"}
_ACCEPTED_EVENT_STATUSES = {"confirmed", "in_progress"}


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
    locked_people_windows: Mapping[str, Sequence] | None = None,
    locked_equipment_windows: Mapping[str, Sequence] | None = None,
    locked_vehicle_windows: Mapping[str, Sequence] | None = None,
    locations_by_id: Mapping[str, object] | None = None,
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
                locked_windows=locked_people_windows or {},
                event=event,
                locations_by_id=locations_by_id or {},
            )
            if not candidates:
                candidates = _fallback_people_candidates(
                    people=people,
                    availability_map=people_availability,
                    required_start=req_start,
                    required_end=req_end,
                    required_hours=req_hours,
                    locked_windows=locked_people_windows or {},
                    event=event,
                    locations_by_id=locations_by_id or {},
                )
            resource_type = "person"
        elif req_type == "equipment_type":
            candidates = _equipment_candidates(
                requirement=requirement,
                equipment=equipment,
                availability_map=equipment_availability,
                required_start=req_start,
                required_end=req_end,
                locked_windows=locked_equipment_windows or {},
                event=event,
                locations_by_id=locations_by_id or {},
            )
            if not candidates:
                candidates = _fallback_equipment_candidates(
                    equipment=equipment,
                    availability_map=equipment_availability,
                    required_start=req_start,
                    required_end=req_end,
                    locked_windows=locked_equipment_windows or {},
                    event=event,
                    locations_by_id=locations_by_id or {},
                )
            resource_type = "equipment"
        elif req_type == "vehicle_type":
            candidates = _vehicle_candidates(
                requirement=requirement,
                vehicles=vehicles,
                availability_map=vehicle_availability,
                required_start=req_start,
                required_end=req_end,
                locked_windows=locked_vehicle_windows or {},
                event=event,
                locations_by_id=locations_by_id or {},
            )
            if not candidates:
                candidates = _fallback_vehicle_candidates(
                    vehicles=vehicles,
                    availability_map=vehicle_availability,
                    required_start=req_start,
                    required_end=req_end,
                    locked_windows=locked_vehicle_windows or {},
                    event=event,
                    locations_by_id=locations_by_id or {},
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
        Location,
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
    locations_by_id = {
        location.location_id: location
        for location in db.execute(select(Location)).scalars().all()
    }

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
    (
        locked_people_windows,
        locked_equipment_windows,
        locked_vehicle_windows,
    ) = _build_priority_locks(
        db,
        event=event,
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
        locked_people_windows=locked_people_windows,
        locked_equipment_windows=locked_equipment_windows,
        locked_vehicle_windows=locked_vehicle_windows,
        locations_by_id=locations_by_id,
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


def _resource_logistics(
    *,
    event,
    resource,
    resource_type: str,
    base_cost_per_hour: Decimal,
    required_hours: Decimal,
    locations_by_id: Mapping[str, object],
) -> dict[str, Decimal | int | str | None]:
    event_location = locations_by_id.get(getattr(event, "location_id", None))
    fallback_attr = {
        "person": "home_base_location_id",
        "equipment": "warehouse_location_id",
        "vehicle": "home_location_id",
    }[resource_type]
    current_location_id = getattr(resource, "current_location_id", None) or getattr(resource, fallback_attr, None)
    current_location = locations_by_id.get(current_location_id)

    if event_location is None or current_location is None:
        return {
            "distance_to_event_km": None,
            "travel_time_minutes": None,
            "logistics_cost": Decimal("0.00"),
            "cost_per_hour_addition": Decimal("0.00"),
            "location_match_score": Decimal("0.82"),
            "location_note": "Current location missing; planner used a conservative logistics score.",
        }
    if current_location_id == getattr(event, "location_id", None):
        return {
            "distance_to_event_km": Decimal("0.00"),
            "travel_time_minutes": 0,
            "logistics_cost": Decimal("0.00"),
            "cost_per_hour_addition": Decimal("0.00"),
            "location_match_score": Decimal("1.00"),
            "location_note": "Already at the event location.",
        }

    distance = _distance_km(current_location, event_location)
    if distance is None:
        return {
            "distance_to_event_km": None,
            "travel_time_minutes": 45,
            "logistics_cost": Decimal("0.00"),
            "cost_per_hour_addition": Decimal("0.00"),
            "location_match_score": Decimal("0.78"),
            "location_note": "Location coordinates missing; planner assumed medium travel friction.",
        }

    travel_minutes = _transport_duration_minutes(distance)
    travel_hours = Decimal(travel_minutes) / Decimal("60")
    km_cost = Decimal("0.00")
    if resource_type == "vehicle":
        km_cost = _decimal_or_zero(getattr(resource, "cost_per_km", None)) * distance * Decimal("2")
    handling_multiplier = {
        "person": Decimal("0.35"),
        "equipment": Decimal("0.55"),
        "vehicle": Decimal("0.25"),
    }[resource_type]
    handling_cost = base_cost_per_hour * travel_hours * handling_multiplier
    logistics_cost = (km_cost + handling_cost).quantize(Decimal("0.01"))
    cost_per_hour_addition = Decimal("0.00")
    if required_hours > 0:
        cost_per_hour_addition = (logistics_cost / required_hours).quantize(Decimal("0.0001"))
    location_match_score = max(
        Decimal("0.25"),
        Decimal("1.00") - min(distance / Decimal("450"), Decimal("0.75")),
    ).quantize(Decimal("0.0001"))
    return {
        "distance_to_event_km": distance.quantize(Decimal("0.01")),
        "travel_time_minutes": travel_minutes,
        "logistics_cost": logistics_cost,
        "cost_per_hour_addition": cost_per_hour_addition,
        "location_match_score": location_match_score,
        "location_note": f"Located {_distance_label(distance)} from the venue; estimated travel {travel_minutes} min.",
    }


def _distance_km(origin, destination) -> Decimal | None:
    if (
        getattr(origin, "latitude", None) is None
        or getattr(origin, "longitude", None) is None
        or getattr(destination, "latitude", None) is None
        or getattr(destination, "longitude", None) is None
    ):
        return None

    lat1 = radians(float(origin.latitude))
    lon1 = radians(float(origin.longitude))
    lat2 = radians(float(destination.latitude))
    lon2 = radians(float(destination.longitude))

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    haversine = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    distance = 6371.0 * 2 * asin(sqrt(haversine))
    return Decimal(str(round(distance, 2)))


def _transport_duration_minutes(distance: Decimal | None) -> int:
    if distance is None:
        return 45
    if distance <= Decimal("0"):
        return 0
    if distance < Decimal("0.25"):
        return 3
    if distance < Decimal("1"):
        return 5
    return max(int((distance / Decimal("50")) * Decimal("60")), 10)


def _distance_label(distance: Decimal) -> str:
    if distance <= Decimal("0"):
        return "the same venue"
    if distance < Decimal("1"):
        meters = int((distance * Decimal("1000")).quantize(Decimal("1")))
        return f"{meters} m"
    return f"{distance.quantize(Decimal('0.1'))} km"


def _people_candidates(
    *,
    requirement,
    people: Sequence,
    availability_map: Mapping[str, Sequence],
    skills_by_person: Mapping[str, set[str]],
    required_start: datetime,
    required_end: datetime,
    required_hours: Decimal,
    locked_windows: Mapping[str, Sequence],
    event,
    locations_by_id: Mapping[str, object],
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
        if _has_lock_overlap(
            locked_windows.get(person.person_id, ()),
            required_start,
            required_end,
        ):
            continue

        cost = _decimal_or_zero(getattr(person, "cost_per_hour", None))
        logistics = _resource_logistics(
            event=event,
            resource=person,
            resource_type="person",
            base_cost_per_hour=cost,
            required_hours=required_hours,
            locations_by_id=locations_by_id,
        )
        reliability_score = _reliability_bonus(getattr(person, "reliability_notes", None))
        candidates.append(
            PlannerCandidate(
                resource_id=person.person_id,
                cost_per_hour=cost,
                score=(_score_from_cost(cost) * logistics["location_match_score"]).quantize(Decimal("0.000001")),
                reliability_score=reliability_score,
                distance_to_event_km=logistics["distance_to_event_km"],
                travel_time_minutes=logistics["travel_time_minutes"],
                logistics_cost=logistics["logistics_cost"],
                location_match_score=logistics["location_match_score"],
                location_note=logistics["location_note"],
                available_from=window.available_from,
                available_to=window.available_to,
            )
        )

    return _sorted_candidates(candidates)


def _fallback_people_candidates(
    *,
    people: Sequence,
    availability_map: Mapping[str, Sequence],
    required_start: datetime,
    required_end: datetime,
    required_hours: Decimal,
    locked_windows: Mapping[str, Sequence],
    event,
    locations_by_id: Mapping[str, object],
) -> list[PlannerCandidate]:
    candidates: list[PlannerCandidate] = []
    for person in people:
        if not getattr(person, "active", True):
            continue
        if not _status_is_available(getattr(person, "availability_status", None)):
            continue
        if not _person_hours_eligible(person, required_hours):
            continue
        window = _find_covering_window(
            availability_map.get(person.person_id, ()), required_start, required_end
        )
        if window is None:
            continue
        if _has_lock_overlap(locked_windows.get(person.person_id, ()), required_start, required_end):
            continue
        cost = _decimal_or_zero(getattr(person, "cost_per_hour", None))
        logistics = _resource_logistics(
            event=event,
            resource=person,
            resource_type="person",
            base_cost_per_hour=cost,
            required_hours=required_hours,
            locations_by_id=locations_by_id,
        )
        candidates.append(
            PlannerCandidate(
                resource_id=person.person_id,
                cost_per_hour=cost,
                score=(_score_from_cost(cost) * Decimal("0.35") * logistics["location_match_score"]).quantize(Decimal("0.000001")),
                reliability_score=_reliability_bonus(getattr(person, "reliability_notes", None)),
                distance_to_event_km=logistics["distance_to_event_km"],
                travel_time_minutes=logistics["travel_time_minutes"],
                logistics_cost=logistics["logistics_cost"],
                location_match_score=logistics["location_match_score"],
                location_note=logistics["location_note"],
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
    locked_windows: Mapping[str, Sequence],
    event,
    locations_by_id: Mapping[str, object],
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
        if _has_lock_overlap(
            locked_windows.get(item.equipment_id, ()),
            required_start,
            required_end,
        ):
            continue

        cost = _decimal_or_zero(getattr(item, "hourly_cost_estimate", None))
        logistics = _resource_logistics(
            event=event,
            resource=item,
            resource_type="equipment",
            base_cost_per_hour=cost,
            required_hours=_window_hours(required_start, required_end),
            locations_by_id=locations_by_id,
        )
        candidates.append(
            PlannerCandidate(
                resource_id=item.equipment_id,
                cost_per_hour=cost,
                score=(_score_from_cost(cost) * logistics["location_match_score"]).quantize(Decimal("0.000001")),
                reliability_score=Decimal("0.08") if getattr(item, "replacement_available", False) else Decimal("0"),
                distance_to_event_km=logistics["distance_to_event_km"],
                travel_time_minutes=logistics["travel_time_minutes"],
                logistics_cost=logistics["logistics_cost"],
                location_match_score=logistics["location_match_score"],
                location_note=logistics["location_note"],
                available_from=window.available_from,
                available_to=window.available_to,
            )
        )

    return _sorted_candidates(candidates)


def _fallback_equipment_candidates(
    *,
    equipment: Sequence,
    availability_map: Mapping[str, Sequence],
    required_start: datetime,
    required_end: datetime,
    locked_windows: Mapping[str, Sequence],
    event,
    locations_by_id: Mapping[str, object],
) -> list[PlannerCandidate]:
    candidates: list[PlannerCandidate] = []
    for item in equipment:
        if not getattr(item, "active", True):
            continue
        if not _status_is_available(getattr(item, "status", None)):
            continue
        window = _find_covering_window(
            availability_map.get(item.equipment_id, ()), required_start, required_end
        )
        if window is None:
            continue
        if _has_lock_overlap(locked_windows.get(item.equipment_id, ()), required_start, required_end):
            continue
        cost = _decimal_or_zero(getattr(item, "hourly_cost_estimate", None))
        logistics = _resource_logistics(
            event=event,
            resource=item,
            resource_type="equipment",
            base_cost_per_hour=cost,
            required_hours=_window_hours(required_start, required_end),
            locations_by_id=locations_by_id,
        )
        candidates.append(
            PlannerCandidate(
                resource_id=item.equipment_id,
                cost_per_hour=cost,
                score=(_score_from_cost(cost) * Decimal("0.35") * logistics["location_match_score"]).quantize(Decimal("0.000001")),
                reliability_score=Decimal("0.08") if getattr(item, "replacement_available", False) else Decimal("0"),
                distance_to_event_km=logistics["distance_to_event_km"],
                travel_time_minutes=logistics["travel_time_minutes"],
                logistics_cost=logistics["logistics_cost"],
                location_match_score=logistics["location_match_score"],
                location_note=logistics["location_note"],
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
    locked_windows: Mapping[str, Sequence],
    event,
    locations_by_id: Mapping[str, object],
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
        if _has_lock_overlap(
            locked_windows.get(vehicle.vehicle_id, ()),
            required_start,
            required_end,
        ):
            continue

        cost = _decimal_or_zero(getattr(vehicle, "cost_per_hour", None))
        if cost == Decimal("0"):
            cost = _decimal_or_zero(getattr(vehicle, "cost_per_km", None))
        logistics = _resource_logistics(
            event=event,
            resource=vehicle,
            resource_type="vehicle",
            base_cost_per_hour=cost,
            required_hours=_window_hours(required_start, required_end),
            locations_by_id=locations_by_id,
        )
        candidates.append(
            PlannerCandidate(
                resource_id=vehicle.vehicle_id,
                cost_per_hour=cost,
                score=(_score_from_cost(cost) * logistics["location_match_score"]).quantize(Decimal("0.000001")),
                reliability_score=Decimal("0.05"),
                distance_to_event_km=logistics["distance_to_event_km"],
                travel_time_minutes=logistics["travel_time_minutes"],
                logistics_cost=logistics["logistics_cost"],
                location_match_score=logistics["location_match_score"],
                location_note=logistics["location_note"],
                available_from=window.available_from,
                available_to=window.available_to,
            )
        )

    return _sorted_candidates(candidates)


def _fallback_vehicle_candidates(
    *,
    vehicles: Sequence,
    availability_map: Mapping[str, Sequence],
    required_start: datetime,
    required_end: datetime,
    locked_windows: Mapping[str, Sequence],
    event,
    locations_by_id: Mapping[str, object],
) -> list[PlannerCandidate]:
    candidates: list[PlannerCandidate] = []
    for vehicle in vehicles:
        if not getattr(vehicle, "active", True):
            continue
        if not _status_is_available(getattr(vehicle, "status", None)):
            continue
        window = _find_covering_window(
            availability_map.get(vehicle.vehicle_id, ()), required_start, required_end
        )
        if window is None:
            continue
        if _has_lock_overlap(locked_windows.get(vehicle.vehicle_id, ()), required_start, required_end):
            continue
        cost = _decimal_or_zero(getattr(vehicle, "cost_per_hour", None))
        if cost == Decimal("0"):
            cost = _decimal_or_zero(getattr(vehicle, "cost_per_km", None))
        logistics = _resource_logistics(
            event=event,
            resource=vehicle,
            resource_type="vehicle",
            base_cost_per_hour=cost,
            required_hours=_window_hours(required_start, required_end),
            locations_by_id=locations_by_id,
        )
        candidates.append(
            PlannerCandidate(
                resource_id=vehicle.vehicle_id,
                cost_per_hour=cost,
                score=(_score_from_cost(cost) * Decimal("0.35") * logistics["location_match_score"]).quantize(Decimal("0.000001")),
                reliability_score=Decimal("0.05"),
                distance_to_event_km=logistics["distance_to_event_km"],
                travel_time_minutes=logistics["travel_time_minutes"],
                logistics_cost=logistics["logistics_cost"],
                location_match_score=logistics["location_match_score"],
                location_note=logistics["location_note"],
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


def _has_lock_overlap(
    locked_windows: Sequence,
    required_start: datetime,
    required_end: datetime,
) -> bool:
    for window in locked_windows:
        if (
            window.available_from < required_end
            and window.available_to > required_start
        ):
            return True
    return False


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


def _build_priority_locks(
    db: Session,
    *,
    event,
) -> tuple[dict[str, list], dict[str, list], dict[str, list]]:
    from sqlalchemy import select

    from app.models.core import Assignment, Event

    lock_rows = (
        db.execute(
            select(Assignment, Event)
            .join(Event, Event.event_id == Assignment.event_id)
            .where(
                Assignment.event_id != event.event_id,
                Assignment.planned_start < event.planned_end,
                Assignment.planned_end > event.planned_start,
            )
        )
        .all()
    )

    people: dict[str, list] = {}
    equipment: dict[str, list] = {}
    vehicles: dict[str, list] = {}
    current_status = _enum_value(getattr(event, "status", None)) or ""

    for assignment, other_event in lock_rows:
        other_status = _enum_value(getattr(other_event, "status", None)) or ""
        if other_status not in _LOCKING_EVENT_STATUSES:
            continue
        if (
            _enum_value(getattr(assignment, "status", None))
            not in _LOCKING_ASSIGNMENT_STATUSES
        ):
            continue
        if not _other_event_has_priority_lock(
            other_event=other_event,
            other_status=other_status,
            current_event=event,
            current_status=current_status,
        ):
            continue

        resource_type = _enum_value(getattr(assignment, "resource_type", None))
        if resource_type == "person" and getattr(assignment, "person_id", None):
            people.setdefault(assignment.person_id, []).append(assignment)
        elif resource_type == "equipment" and getattr(assignment, "equipment_id", None):
            equipment.setdefault(assignment.equipment_id, []).append(assignment)
        elif resource_type == "vehicle" and getattr(assignment, "vehicle_id", None):
            vehicles.setdefault(assignment.vehicle_id, []).append(assignment)

    return people, equipment, vehicles


def _event_priority_key(event) -> tuple[float, str]:
    created_at = getattr(event, "created_at", None)
    created_ts = 0.0
    if isinstance(created_at, datetime):
        created_ts = created_at.timestamp()
    event_id = getattr(event, "event_id", "")
    return created_ts, event_id


def _other_event_has_priority_lock(
    *,
    other_event,
    other_status: str,
    current_event,
    current_status: str,
) -> bool:
    other_accepted = other_status in _ACCEPTED_EVENT_STATUSES
    current_accepted = current_status in _ACCEPTED_EVENT_STATUSES
    if other_accepted and not current_accepted:
        return True
    if current_accepted and not other_accepted:
        return False
    return _event_priority_key(other_event) <= _event_priority_key(current_event)
