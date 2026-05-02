from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.ai import (
    PlannerRecommendation,
    PlannerRecommendationAssignment,
    PlannerRun,
    PlannerRunStatus,
)
from app.models.core import (
    Assignment,
    AssignmentResourceType,
    AssignmentStatus,
    Event,
    EventStatus,
    Location,
    ResourcePerson,
    TransportLeg,
    Vehicle,
)
from app.schemas.planner import (
    GeneratedPlanAssignment,
    GeneratePlanResponse,
)
from app.services.ortools_service import (
    PlannerAssignment,
    PlannerRequirement,
    PlannerService,
)
from app.services.planner_input_builder import PlannerInputError, load_planner_input


class PlanGenerationError(ValueError):
    pass


def generate_plan(
    db: Session,
    *,
    event_id: str,
    initiated_by: str | None = None,
    trigger_reason: str = "manual",
    commit_to_assignments: bool = True,
) -> GeneratePlanResponse:
    event = db.get(Event, event_id)
    if event is None:
        raise PlannerInputError("Event not found")

    model = load_planner_input(db, event_id)
    planner_run = PlannerRun(
        objective_version="phase-4-cp-03-v1",
        initiated_by=initiated_by,
        trigger_reason=trigger_reason,
        input_snapshot=_jsonable(model),
    )
    db.add(planner_run)
    db.flush()

    try:
        result = PlannerService().solve(model)
        requirement_by_id = {
            requirement.requirement_id: requirement for requirement in model.requirements
        }
        recommendation = _create_recommendation(
            db=db,
            event=event,
            planner_run=planner_run,
            requirements=requirement_by_id,
            assignments=result.assignments,
            total_cost=result.estimated_cost,
            selected=commit_to_assignments,
        )

        assignment_ids: list[str] = []
        transport_leg_ids: list[str] = []
        if commit_to_assignments:
            assignment_ids = _commit_assignments(
                db=db,
                event=event,
                planner_run=planner_run,
                requirements=requirement_by_id,
                assignments=result.assignments,
            )
            transport_leg_ids = _create_transport_legs(
                db=db,
                event=event,
                planner_run=planner_run,
                assignments=result.assignments,
                requirements=requirement_by_id,
            )
            if _is_fully_assigned(result.assignments):
                event.status = EventStatus.planned

        planner_run.finished_at = datetime.utcnow()
        planner_run.run_status = PlannerRunStatus.completed
        planner_run.total_cost = _money(result.estimated_cost)
        planner_run.notes = _run_notes(result.assignments)
        db.commit()
        db.refresh(recommendation)

        return GeneratePlanResponse(
            event_id=event_id,
            planner_run_id=planner_run.planner_run_id,
            recommendation_id=recommendation.recommendation_id,
            plan_id=result.plan_id,
            solver=result.solver,
            is_fully_assigned=_is_fully_assigned(result.assignments),
            assignments=[
                _response_assignment(assignment, requirement_by_id)
                for assignment in result.assignments
            ],
            assignment_ids=assignment_ids,
            transport_leg_ids=transport_leg_ids,
            estimated_cost=_money(result.estimated_cost),
        )
    except Exception as exc:
        planner_run.finished_at = datetime.utcnow()
        planner_run.run_status = PlannerRunStatus.failed
        planner_run.notes = str(exc)
        db.commit()
        raise PlanGenerationError(str(exc)) from exc


def _create_recommendation(
    *,
    db: Session,
    event: Event,
    planner_run: PlannerRun,
    requirements: dict[str, PlannerRequirement],
    assignments: list[PlannerAssignment],
    total_cost: Decimal,
    selected: bool,
) -> PlannerRecommendation:
    recommendation = PlannerRecommendation(
        planner_run_id=planner_run.planner_run_id,
        event_id=event.event_id,
        expected_cost=_money(total_cost),
        expected_duration_minutes=_event_duration_minutes(event),
        expected_risk=_risk_from_unassigned(assignments),
        selected_for_execution=selected,
        rationale=_recommendation_rationale(assignments),
    )
    db.add(recommendation)
    db.flush()

    for assignment in assignments:
        requirement = requirements[assignment.requirement_id]
        for resource_id in assignment.resource_ids:
            db.add(
                PlannerRecommendationAssignment(
                    recommendation_id=recommendation.recommendation_id,
                    resource_type=_assignment_resource_type(requirement),
                    **_resource_fk(requirement.resource_type, resource_id),
                    assignment_role=_assignment_role(requirement),
                    planned_start=requirement.required_start,
                    planned_end=requirement.required_end,
                    risk_score=Decimal("0"),
                    cost_estimate=_money(_resource_cost_share(assignment)),
                )
            )

    return recommendation


def _commit_assignments(
    *,
    db: Session,
    event: Event,
    planner_run: PlannerRun,
    requirements: dict[str, PlannerRequirement],
    assignments: list[PlannerAssignment],
) -> list[str]:
    db.execute(
        delete(Assignment).where(
            Assignment.event_id == event.event_id,
            Assignment.is_manual_override.is_(False),
            Assignment.status.in_(
                [AssignmentStatus.proposed, AssignmentStatus.planned]
            ),
        )
    )
    db.flush()

    assignment_ids: list[str] = []
    for assignment in assignments:
        requirement = requirements[assignment.requirement_id]
        for resource_id in assignment.resource_ids:
            core_assignment = Assignment(
                event_id=event.event_id,
                resource_type=_assignment_resource_type(requirement),
                **_resource_fk(requirement.resource_type, resource_id),
                assignment_role=_assignment_role(requirement),
                planned_start=requirement.required_start,
                planned_end=requirement.required_end,
                status=AssignmentStatus.planned,
                planner_run_id=planner_run.planner_run_id,
                is_manual_override=False,
                notes=f"Generated from requirement {requirement.requirement_id}",
            )
            db.add(core_assignment)
            db.flush()
            assignment_ids.append(core_assignment.assignment_id)

    return assignment_ids


def _create_transport_legs(
    *,
    db: Session,
    event: Event,
    planner_run: PlannerRun,
    assignments: list[PlannerAssignment],
    requirements: dict[str, PlannerRequirement],
) -> list[str]:
    if not event.requires_transport:
        return []

    db.execute(
        delete(TransportLeg).where(
            TransportLeg.event_id == event.event_id,
            TransportLeg.notes.like("Generated by planner run%"),
        )
    )
    db.flush()

    driver_id = _first_driver(db, assignments, requirements)
    leg_ids: list[str] = []
    for vehicle_id in _assigned_vehicle_ids(assignments, requirements):
        vehicle = db.get(Vehicle, vehicle_id)
        if vehicle is None or vehicle.home_location_id is None:
            continue
        if vehicle.home_location_id == event.location_id:
            continue

        origin = db.get(Location, vehicle.home_location_id)
        destination = db.get(Location, event.location_id)
        if origin is None or destination is None:
            continue

        distance = _distance_km(origin, destination)
        duration_minutes = _transport_duration_minutes(distance)
        transport_leg = TransportLeg(
            event_id=event.event_id,
            vehicle_id=vehicle.vehicle_id,
            driver_person_id=driver_id,
            origin_location_id=origin.location_id,
            destination_location_id=destination.location_id,
            planned_departure=event.planned_start - timedelta(minutes=duration_minutes),
            planned_arrival=event.planned_start,
            estimated_distance_km=distance,
            estimated_duration_minutes=duration_minutes,
            notes=f"Generated by planner run {planner_run.planner_run_id}",
        )
        db.add(transport_leg)
        db.flush()
        leg_ids.append(transport_leg.transport_leg_id)

    return leg_ids


def _response_assignment(
    assignment: PlannerAssignment,
    requirements: dict[str, PlannerRequirement],
) -> GeneratedPlanAssignment:
    requirement = requirements[assignment.requirement_id]
    return GeneratedPlanAssignment(
        requirement_id=assignment.requirement_id,
        resource_type=requirement.resource_type,
        resource_ids=assignment.resource_ids,
        unassigned_count=assignment.unassigned_count,
        estimated_cost=_money(assignment.estimated_cost),
    )


def _assignment_resource_type(requirement: PlannerRequirement) -> AssignmentResourceType:
    if requirement.resource_type == "person":
        return AssignmentResourceType.person
    if requirement.resource_type == "equipment":
        return AssignmentResourceType.equipment
    if requirement.resource_type == "vehicle":
        return AssignmentResourceType.vehicle
    raise PlanGenerationError(f"Unsupported resource type: {requirement.resource_type}")


def _resource_fk(resource_type: str, resource_id: str) -> dict[str, str]:
    if resource_type == "person":
        return {"person_id": resource_id}
    if resource_type == "equipment":
        return {"equipment_id": resource_id}
    if resource_type == "vehicle":
        return {"vehicle_id": resource_id}
    raise PlanGenerationError(f"Unsupported resource type: {resource_type}")


def _assignment_role(requirement: PlannerRequirement) -> str:
    return f"requirement:{requirement.requirement_id}"


def _resource_cost_share(assignment: PlannerAssignment) -> Decimal:
    if not assignment.resource_ids:
        return Decimal("0")
    return assignment.estimated_cost / Decimal(len(assignment.resource_ids))


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _event_duration_minutes(event: Event) -> int:
    seconds = (event.planned_end - event.planned_start).total_seconds()
    return int(max(seconds, 0) // 60)


def _risk_from_unassigned(assignments: list[PlannerAssignment]) -> Decimal:
    unassigned = sum(assignment.unassigned_count for assignment in assignments)
    return Decimal(str(unassigned))


def _recommendation_rationale(assignments: list[PlannerAssignment]) -> str:
    if _is_fully_assigned(assignments):
        return "All requirements assigned by deterministic planner."
    unassigned = sum(assignment.unassigned_count for assignment in assignments)
    return f"Partial plan generated with {unassigned} unassigned resource slot(s)."


def _run_notes(assignments: list[PlannerAssignment]) -> str:
    if _is_fully_assigned(assignments):
        return "Planner completed with full assignment coverage."
    unassigned = sum(assignment.unassigned_count for assignment in assignments)
    return f"Planner completed with {unassigned} unassigned resource slot(s)."


def _is_fully_assigned(assignments: list[PlannerAssignment]) -> bool:
    return all(assignment.unassigned_count == 0 for assignment in assignments)


def _assigned_vehicle_ids(
    assignments: list[PlannerAssignment],
    requirements: dict[str, PlannerRequirement],
) -> list[str]:
    vehicle_ids: list[str] = []
    for assignment in assignments:
        requirement = requirements[assignment.requirement_id]
        if requirement.resource_type == "vehicle":
            vehicle_ids.extend(assignment.resource_ids)
    return vehicle_ids


def _first_driver(
    db: Session,
    assignments: list[PlannerAssignment],
    requirements: dict[str, PlannerRequirement],
) -> str | None:
    for assignment in assignments:
        requirement = requirements[assignment.requirement_id]
        if requirement.resource_type != "person":
            continue
        for person_id in assignment.resource_ids:
            person = db.get(ResourcePerson, person_id)
            if (
                person is not None
                and getattr(person.role, "value", person.role) == "driver"
            ):
                return person.person_id
    return None


def _distance_km(origin: Location, destination: Location) -> Decimal | None:
    if (
        origin.latitude is None
        or origin.longitude is None
        or destination.latitude is None
        or destination.longitude is None
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
        return 60
    return max(int((distance / Decimal("50")) * Decimal("60")), 15)


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value
