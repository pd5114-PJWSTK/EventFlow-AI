from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.core import (
    Equipment,
    EquipmentAvailability,
    Event,
    EventRequirement,
    PeopleAvailability,
    PersonSkill,
    RequirementType,
    ResourcePerson,
    ResourceStatus,
    Vehicle,
    VehicleAvailability,
)
from app.schemas.planner import ConstraintCheckResponse, ConstraintGap


class ValidationError(ValueError):
    pass


def _required_window(
    event: Event, requirement: EventRequirement
) -> tuple[datetime, datetime]:
    start = requirement.required_start or event.planned_start
    end = requirement.required_end or event.planned_end
    return start, end


def _required_quantity(requirement: EventRequirement) -> int:
    # Quantity is stored as Decimal; use ceiling so fractional values never under-allocate.
    return int(requirement.quantity.to_integral_value(rounding=ROUND_CEILING))


def _window_hours(start: datetime, end: datetime) -> Decimal:
    return Decimal(str((end - start).total_seconds() / 3600.0))


def _person_available(
    db: Session, person_id: str, start: datetime, end: datetime
) -> bool:
    window = db.execute(
        select(PeopleAvailability)
        .where(
            and_(
                PeopleAvailability.person_id == person_id,
                PeopleAvailability.is_available.is_(True),
                PeopleAvailability.available_from <= start,
                PeopleAvailability.available_to >= end,
            )
        )
        .limit(1)
    ).scalar_one_or_none()
    return window is not None


def _equipment_available(
    db: Session, equipment_id: str, start: datetime, end: datetime
) -> bool:
    window = db.execute(
        select(EquipmentAvailability)
        .where(
            and_(
                EquipmentAvailability.equipment_id == equipment_id,
                EquipmentAvailability.is_available.is_(True),
                EquipmentAvailability.available_from <= start,
                EquipmentAvailability.available_to >= end,
            )
        )
        .limit(1)
    ).scalar_one_or_none()
    return window is not None


def _vehicle_available(
    db: Session, vehicle_id: str, start: datetime, end: datetime
) -> bool:
    window = db.execute(
        select(VehicleAvailability)
        .where(
            and_(
                VehicleAvailability.vehicle_id == vehicle_id,
                VehicleAvailability.is_available.is_(True),
                VehicleAvailability.available_from <= start,
                VehicleAvailability.available_to >= end,
            )
        )
        .limit(1)
    ).scalar_one_or_none()
    return window is not None


def _append_shortage_gap(
    gaps: list[ConstraintGap],
    code: str,
    requirement_id: str,
    expected: int,
    available: int,
    mandatory: bool,
) -> None:
    severity = "critical" if mandatory else "warning"
    gaps.append(
        ConstraintGap(
            code=code,
            requirement_id=requirement_id,
            severity=severity,
            message=f"required={expected}, available={available}",
        )
    )


def _append_availability_gap(
    gaps: list[ConstraintGap],
    requirement_id: str,
    expected: int,
    available: int,
    mandatory: bool,
) -> None:
    severity = "critical" if mandatory else "warning"
    gaps.append(
        ConstraintGap(
            code="AVAILABILITY_WINDOW_MISMATCH",
            requirement_id=requirement_id,
            severity=severity,
            message=f"required={expected}, available={available}; candidates exist but are not available in required window",
        )
    )


def validate_event_constraints(db: Session, event_id: str) -> ConstraintCheckResponse:
    event = db.get(Event, event_id)
    if event is None:
        raise ValidationError("Event not found")

    gaps: list[ConstraintGap] = []
    estimated_cost = Decimal("0.00")

    for requirement in event.requirements:
        req_start, req_end = _required_window(event, requirement)
        required_qty = _required_quantity(requirement)

        if req_end <= req_start:
            gaps.append(
                ConstraintGap(
                    code="INVALID_REQUIREMENT_WINDOW",
                    requirement_id=requirement.requirement_id,
                    severity="critical" if requirement.mandatory else "warning",
                    message="required_end must be after required_start",
                )
            )
            continue

        if req_start < event.planned_start or req_end > event.planned_end:
            gaps.append(
                ConstraintGap(
                    code="TIME_WINDOW_OUT_OF_EVENT",
                    requirement_id=requirement.requirement_id,
                    severity="critical" if requirement.mandatory else "warning",
                    message="requirement window must fit inside event planned window",
                )
            )
            continue

        if requirement.requirement_type == RequirementType.person_role:
            people = (
                db.execute(
                    select(ResourcePerson).where(
                        and_(
                            ResourcePerson.role == requirement.role_required,
                            ResourcePerson.active.is_(True),
                            ResourcePerson.availability_status.in_(
                                [ResourceStatus.available, ResourceStatus.reserved]
                            ),
                        )
                    )
                )
                .scalars()
                .all()
            )
            candidate_count = len(people)
            available_people = [
                p
                for p in people
                if _person_available(db, p.person_id, req_start, req_end)
            ]
            if len(available_people) < required_qty:
                if candidate_count >= required_qty:
                    _append_availability_gap(
                        gaps,
                        requirement_id=requirement.requirement_id,
                        expected=required_qty,
                        available=len(available_people),
                        mandatory=requirement.mandatory,
                    )
                else:
                    _append_shortage_gap(
                        gaps,
                        code="INSUFFICIENT_ROLE",
                        requirement_id=requirement.requirement_id,
                        expected=required_qty,
                        available=len(available_people),
                        mandatory=requirement.mandatory,
                    )
            for person in available_people[:required_qty]:
                if person.cost_per_hour is not None:
                    estimated_cost += person.cost_per_hour * _window_hours(
                        req_start, req_end
                    )

        elif requirement.requirement_type == RequirementType.person_skill:
            people = (
                db.execute(
                    select(ResourcePerson)
                    .join(
                        PersonSkill, PersonSkill.person_id == ResourcePerson.person_id
                    )
                    .where(
                        and_(
                            PersonSkill.skill_id == requirement.skill_id,
                            ResourcePerson.active.is_(True),
                            ResourcePerson.availability_status.in_(
                                [ResourceStatus.available, ResourceStatus.reserved]
                            ),
                        )
                    )
                )
                .scalars()
                .all()
            )
            candidate_count = len(people)
            available_people = [
                p
                for p in people
                if _person_available(db, p.person_id, req_start, req_end)
            ]
            if len(available_people) < required_qty:
                if candidate_count >= required_qty:
                    _append_availability_gap(
                        gaps,
                        requirement_id=requirement.requirement_id,
                        expected=required_qty,
                        available=len(available_people),
                        mandatory=requirement.mandatory,
                    )
                else:
                    _append_shortage_gap(
                        gaps,
                        code="INSUFFICIENT_SKILL",
                        requirement_id=requirement.requirement_id,
                        expected=required_qty,
                        available=len(available_people),
                        mandatory=requirement.mandatory,
                    )
            for person in available_people[:required_qty]:
                if person.cost_per_hour is not None:
                    estimated_cost += person.cost_per_hour * _window_hours(
                        req_start, req_end
                    )

        elif requirement.requirement_type == RequirementType.equipment_type:
            equipment = (
                db.execute(
                    select(Equipment).where(
                        and_(
                            Equipment.equipment_type_id
                            == requirement.equipment_type_id,
                            Equipment.active.is_(True),
                            Equipment.status.in_(
                                [ResourceStatus.available, ResourceStatus.reserved]
                            ),
                        )
                    )
                )
                .scalars()
                .all()
            )
            candidate_count = len(equipment)
            available_equipment = [
                eq
                for eq in equipment
                if _equipment_available(db, eq.equipment_id, req_start, req_end)
            ]
            if len(available_equipment) < required_qty:
                if candidate_count >= required_qty:
                    _append_availability_gap(
                        gaps,
                        requirement_id=requirement.requirement_id,
                        expected=required_qty,
                        available=len(available_equipment),
                        mandatory=requirement.mandatory,
                    )
                else:
                    _append_shortage_gap(
                        gaps,
                        code="INSUFFICIENT_EQUIPMENT",
                        requirement_id=requirement.requirement_id,
                        expected=required_qty,
                        available=len(available_equipment),
                        mandatory=requirement.mandatory,
                    )
            for item in available_equipment[:required_qty]:
                if item.hourly_cost_estimate is not None:
                    estimated_cost += item.hourly_cost_estimate * _window_hours(
                        req_start, req_end
                    )

        elif requirement.requirement_type == RequirementType.vehicle_type:
            vehicles = (
                db.execute(
                    select(Vehicle).where(
                        and_(
                            Vehicle.vehicle_type == requirement.vehicle_type_required,
                            Vehicle.active.is_(True),
                            Vehicle.status.in_(
                                [ResourceStatus.available, ResourceStatus.reserved]
                            ),
                        )
                    )
                )
                .scalars()
                .all()
            )
            candidate_count = len(vehicles)
            available_vehicles = [
                v
                for v in vehicles
                if _vehicle_available(db, v.vehicle_id, req_start, req_end)
            ]
            if len(available_vehicles) < required_qty:
                if candidate_count >= required_qty:
                    _append_availability_gap(
                        gaps,
                        requirement_id=requirement.requirement_id,
                        expected=required_qty,
                        available=len(available_vehicles),
                        mandatory=requirement.mandatory,
                    )
                else:
                    _append_shortage_gap(
                        gaps,
                        code="INSUFFICIENT_VEHICLE",
                        requirement_id=requirement.requirement_id,
                        expected=required_qty,
                        available=len(available_vehicles),
                        mandatory=requirement.mandatory,
                    )
            for vehicle in available_vehicles[:required_qty]:
                if vehicle.cost_per_hour is not None:
                    estimated_cost += vehicle.cost_per_hour * _window_hours(
                        req_start, req_end
                    )

    budget_exceeded = False
    if event.budget_estimate is not None and estimated_cost > event.budget_estimate:
        budget_exceeded = True
        gaps.append(
            ConstraintGap(
                code="BUDGET_EXCEEDED",
                requirement_id=None,
                severity="critical",
                message=f"estimated_cost={estimated_cost} exceeds budget={event.budget_estimate}",
            )
        )

    has_blocking_gap = any(gap.severity == "critical" for gap in gaps)

    return ConstraintCheckResponse(
        event_id=event.event_id,
        checked_at=datetime.now(timezone.utc),
        is_supportable=not has_blocking_gap,
        gaps=gaps,
        estimated_cost=estimated_cost,
        budget_available=event.budget_estimate,
        budget_exceeded=budget_exceeded,
    )
