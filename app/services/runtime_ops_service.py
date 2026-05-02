from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.core import Assignment, AssignmentStatus, Event, EventStatus
from app.models.ops import (
    ActualTiming,
    EventExecutionLog,
    EventOutcome,
    Incident,
    OpsLogType,
    ResourceCheckpoint,
)
from app.schemas.runtime_ops import (
    RuntimeCheckpointRequest,
    RuntimeCheckpointResponse,
    RuntimeCompleteRequest,
    RuntimeCompleteResponse,
    RuntimeIncidentRequest,
    RuntimeIncidentResponse,
    RuntimeStartRequest,
    RuntimeStartResponse,
)
from app.services.runtime_notification_service import enqueue_runtime_notification
from app.services.planner_generation_service import attach_plan_outcome_feedback
from app.services.datetime_service import minutes_between_utc, to_utc
from app.services.observability_service import emit_event


class RuntimeOpsError(ValueError):
    pass


def start_event_execution(
    db: Session,
    *,
    event_id: str,
    payload: RuntimeStartRequest,
    actor_user_id: str | None = None,
    actor_username: str | None = None,
) -> RuntimeStartResponse:
    event = _get_event_or_error(db, event_id, for_update=True)
    started_at = to_utc(payload.started_at) or datetime.now(UTC)

    event.status = EventStatus.in_progress

    log = EventExecutionLog(
        event_id=event.event_id,
        log_type=OpsLogType.event_started,
        author_type=payload.author_type,
        author_reference=payload.author_reference or actor_username,
        author_user_id=actor_user_id,
        timestamp_at=started_at,
        message=payload.message or "Event execution started.",
        meta={"phase_name": payload.phase_name.value},
    )
    db.add(log)

    timing = ActualTiming(
        event_id=event.event_id,
        phase_name=payload.phase_name,
        planned_start=event.planned_start,
        planned_end=event.planned_end,
        actual_start=started_at,
        delay_reason_code=payload.delay_reason_code,
        notes=payload.notes,
    )
    db.add(timing)
    db.commit()
    db.refresh(log)
    db.refresh(timing)
    emit_event(
        "runtime.start",
        event_id=event.event_id,
        timing_id=timing.timing_id,
        log_id=log.log_id,
        phase_name=payload.phase_name.value,
    )
    enqueue_runtime_notification(
        event_id=event.event_id,
        notification_type="event_started",
        payload={
            "log_id": log.log_id,
            "timing_id": timing.timing_id,
            "phase_name": payload.phase_name.value,
            "event_status": event.status.value,
        },
    )

    return RuntimeStartResponse(
        event_id=event.event_id,
        event_status=event.status.value,
        log_id=log.log_id,
        timing_id=timing.timing_id,
    )


def create_resource_checkpoint(
    db: Session,
    *,
    event_id: str,
    payload: RuntimeCheckpointRequest,
    actor_user_id: str | None = None,
    actor_username: str | None = None,
) -> RuntimeCheckpointResponse:
    event = _get_event_or_error(db, event_id, for_update=True)
    checkpoint_time = to_utc(payload.checkpoint_time) or datetime.now(UTC)
    effective_assignment_id = payload.assignment_id or _resolve_assignment_for_checkpoint(
        db,
        event_id=event.event_id,
        resource_type=payload.resource_type.value,
        person_id=payload.person_id,
        equipment_id=payload.equipment_id,
        vehicle_id=payload.vehicle_id,
    )

    checkpoint = ResourceCheckpoint(
        event_id=event.event_id,
        assignment_id=effective_assignment_id,
        resource_type=payload.resource_type,
        person_id=payload.person_id,
        equipment_id=payload.equipment_id,
        vehicle_id=payload.vehicle_id,
        checkpoint_type=payload.checkpoint_type,
        checkpoint_time=checkpoint_time,
        latitude=payload.latitude,
        longitude=payload.longitude,
        notes=payload.notes,
    )
    db.add(checkpoint)

    log = EventExecutionLog(
        event_id=event.event_id,
        assignment_id=effective_assignment_id,
        log_type=OpsLogType.note,
        author_type=payload.author_type,
        author_reference=payload.author_reference or actor_username,
        author_user_id=actor_user_id,
        timestamp_at=checkpoint_time,
        message=payload.message
        or f"Resource checkpoint recorded: {payload.checkpoint_type}.",
        meta={
            "resource_type": payload.resource_type.value,
            "person_id": payload.person_id,
            "equipment_id": payload.equipment_id,
            "vehicle_id": payload.vehicle_id,
        },
    )
    db.add(log)
    _mark_assignment_consumed(
        db,
        assignment_id=effective_assignment_id,
        consumed_at=checkpoint_time,
    )

    db.commit()
    db.refresh(checkpoint)
    db.refresh(log)
    emit_event(
        "runtime.checkpoint",
        event_id=event.event_id,
        checkpoint_id=checkpoint.checkpoint_id,
        assignment_id=payload.assignment_id,
        resource_type=payload.resource_type.value,
    )
    enqueue_runtime_notification(
        event_id=event.event_id,
        notification_type="resource_checkpoint",
        payload={
            "checkpoint_id": checkpoint.checkpoint_id,
            "log_id": log.log_id,
            "resource_type": payload.resource_type.value,
            "checkpoint_type": payload.checkpoint_type,
        },
    )
    return RuntimeCheckpointResponse(
        event_id=event.event_id, checkpoint_id=checkpoint.checkpoint_id, log_id=log.log_id
    )


def report_incident(
    db: Session,
    *,
    event_id: str,
    payload: RuntimeIncidentRequest,
    actor_user_id: str | None = None,
    actor_username: str | None = None,
) -> RuntimeIncidentResponse:
    event = _get_event_or_error(db, event_id, for_update=True)
    reported_at = to_utc(payload.reported_at) or datetime.now(UTC)

    incident = Incident(
        event_id=event.event_id,
        assignment_id=payload.assignment_id,
        incident_type=payload.incident_type,
        severity=payload.severity,
        reported_at=reported_at,
        reported_by=payload.reported_by or actor_username,
        reported_by_user_id=actor_user_id,
        root_cause=payload.root_cause,
        description=payload.description,
        cost_impact=payload.cost_impact,
        sla_impact=payload.sla_impact,
    )
    db.add(incident)

    log = EventExecutionLog(
        event_id=event.event_id,
        assignment_id=payload.assignment_id,
        log_type=OpsLogType.incident_reported,
        author_type=payload.author_type,
        author_reference=payload.author_reference or actor_username,
        author_user_id=actor_user_id,
        timestamp_at=reported_at,
        message=payload.description,
        meta={
            "incident_type": payload.incident_type.value,
            "severity": payload.severity.value,
            "sla_impact": payload.sla_impact,
        },
    )
    db.add(log)
    _mark_assignment_consumed(
        db,
        assignment_id=payload.assignment_id,
        consumed_at=reported_at,
    )
    db.commit()
    db.refresh(incident)
    db.refresh(log)
    emit_event(
        "runtime.incident",
        event_id=event.event_id,
        incident_id=incident.incident_id,
        incident_type=payload.incident_type.value,
        severity=payload.severity.value,
    )
    enqueue_runtime_notification(
        event_id=event.event_id,
        notification_type="incident_reported",
        payload={
            "incident_id": incident.incident_id,
            "log_id": log.log_id,
            "incident_type": payload.incident_type.value,
            "severity": payload.severity.value,
            "sla_impact": payload.sla_impact,
        },
    )
    return RuntimeIncidentResponse(
        event_id=event.event_id, incident_id=incident.incident_id, log_id=log.log_id
    )


def complete_event_execution(
    db: Session,
    *,
    event_id: str,
    payload: RuntimeCompleteRequest,
    actor_user_id: str | None = None,
    actor_username: str | None = None,
) -> RuntimeCompleteResponse:
    event = _get_event_or_error(db, event_id, for_update=True)
    completed_at = to_utc(payload.completed_at) or datetime.now(UTC)

    event.status = EventStatus.completed

    outcome = db.get(EventOutcome, event.event_id)
    if outcome is None:
        outcome = EventOutcome(event_id=event.event_id)
        db.add(outcome)

    outcome.finished_on_time = payload.finished_on_time
    outcome.total_delay_minutes = payload.total_delay_minutes
    outcome.actual_cost = payload.actual_cost
    outcome.overtime_cost = payload.overtime_cost
    outcome.transport_cost = payload.transport_cost
    outcome.sla_breached = payload.sla_breached
    outcome.client_satisfaction_score = payload.client_satisfaction_score
    outcome.internal_quality_score = payload.internal_quality_score
    outcome.margin_estimate = payload.margin_estimate
    outcome.summary_notes = payload.summary_notes
    outcome.closed_at = completed_at
    attach_plan_outcome_feedback(
        db,
        event_id=event.event_id,
        finished_on_time=payload.finished_on_time,
        total_delay_minutes=payload.total_delay_minutes,
        actual_cost=payload.actual_cost,
        sla_breached=payload.sla_breached,
        closed_at=completed_at,
    )

    log = EventExecutionLog(
        event_id=event.event_id,
        log_type=OpsLogType.event_completed,
        author_type=payload.author_type,
        author_reference=payload.author_reference or actor_username,
        author_user_id=actor_user_id,
        timestamp_at=completed_at,
        message=payload.message or "Event execution completed.",
        meta={"phase_name": payload.phase_name.value},
    )
    db.add(log)

    timing = _get_open_timing(db, event.event_id, payload.phase_name)
    if timing is None:
        timing = ActualTiming(
            event_id=event.event_id,
            phase_name=payload.phase_name,
            planned_start=event.planned_start,
            planned_end=event.planned_end,
            actual_end=completed_at,
            delay_reason_code=payload.delay_reason_code,
            notes=payload.summary_notes,
        )
        db.add(timing)
    else:
        timing.actual_end = completed_at
        timing.delay_reason_code = payload.delay_reason_code
        if payload.summary_notes:
            timing.notes = payload.summary_notes
        if timing.planned_end is not None and timing.actual_end is not None:
            timing.delay_minutes = minutes_between_utc(
                timing.actual_end, timing.planned_end
            )

    db.commit()
    db.refresh(outcome)
    db.refresh(log)
    db.refresh(timing)
    emit_event(
        "runtime.complete",
        event_id=event.event_id,
        timing_id=timing.timing_id,
        outcome_event_id=outcome.event_id,
        sla_breached=payload.sla_breached,
    )
    enqueue_runtime_notification(
        event_id=event.event_id,
        notification_type="event_completed",
        payload={
            "outcome_event_id": outcome.event_id,
            "log_id": log.log_id,
            "timing_id": timing.timing_id,
            "event_status": event.status.value,
            "sla_breached": payload.sla_breached,
        },
    )

    return RuntimeCompleteResponse(
        event_id=event.event_id,
        event_status=event.status.value,
        outcome_event_id=outcome.event_id,
        log_id=log.log_id,
        timing_id=timing.timing_id,
    )


def _get_event_or_error(db: Session, event_id: str, *, for_update: bool = False) -> Event:
    query = db.query(Event).filter(Event.event_id == event_id)
    if for_update:
        query = query.with_for_update()
    event = query.first()
    if event is None:
        raise RuntimeOpsError("Event not found")
    return event


def _get_open_timing(
    db: Session, event_id: str, phase_name
) -> ActualTiming | None:
    return (
        db.query(ActualTiming)
        .filter(
            ActualTiming.event_id == event_id,
            ActualTiming.phase_name == phase_name,
            ActualTiming.actual_end.is_(None),
        )
        .order_by(ActualTiming.created_at.desc())
        .first()
    )


def _mark_assignment_consumed(
    db: Session,
    *,
    assignment_id: str | None,
    consumed_at: datetime,
) -> None:
    if not assignment_id:
        return
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        return
    assignment.is_consumed_in_execution = True
    assignment.consumed_at = consumed_at
    db.add(assignment)


def _resolve_assignment_for_checkpoint(
    db: Session,
    *,
    event_id: str,
    resource_type: str,
    person_id: str | None,
    equipment_id: str | None,
    vehicle_id: str | None,
) -> str | None:
    query = db.query(Assignment).filter(
        Assignment.event_id == event_id,
        Assignment.status.in_(
            [
                AssignmentStatus.proposed,
                AssignmentStatus.planned,
                AssignmentStatus.confirmed,
                AssignmentStatus.active,
            ]
        ),
    )
    if resource_type == "person" and person_id:
        query = query.filter(Assignment.person_id == person_id)
    elif resource_type == "equipment" and equipment_id:
        query = query.filter(Assignment.equipment_id == equipment_id)
    elif resource_type == "vehicle" and vehicle_id:
        query = query.filter(Assignment.vehicle_id == vehicle_id)
    else:
        return None

    assignment = query.order_by(Assignment.created_at.desc()).first()
    if assignment is None:
        return None
    return assignment.assignment_id
