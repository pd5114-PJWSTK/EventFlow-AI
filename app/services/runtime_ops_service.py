from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.core import Event, EventStatus
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


class RuntimeOpsError(ValueError):
    pass


def start_event_execution(
    db: Session, *, event_id: str, payload: RuntimeStartRequest
) -> RuntimeStartResponse:
    event = _get_event_or_error(db, event_id)
    started_at = payload.started_at or datetime.utcnow()

    event.status = EventStatus.in_progress

    log = EventExecutionLog(
        event_id=event.event_id,
        log_type=OpsLogType.event_started,
        author_type=payload.author_type,
        author_reference=payload.author_reference,
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

    return RuntimeStartResponse(
        event_id=event.event_id,
        event_status=event.status.value,
        log_id=log.log_id,
        timing_id=timing.timing_id,
    )


def create_resource_checkpoint(
    db: Session, *, event_id: str, payload: RuntimeCheckpointRequest
) -> RuntimeCheckpointResponse:
    event = _get_event_or_error(db, event_id)
    checkpoint_time = payload.checkpoint_time or datetime.utcnow()

    checkpoint = ResourceCheckpoint(
        event_id=event.event_id,
        assignment_id=payload.assignment_id,
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
        assignment_id=payload.assignment_id,
        log_type=OpsLogType.note,
        author_type=payload.author_type,
        author_reference=payload.author_reference,
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

    db.commit()
    db.refresh(checkpoint)
    db.refresh(log)
    return RuntimeCheckpointResponse(
        event_id=event.event_id, checkpoint_id=checkpoint.checkpoint_id, log_id=log.log_id
    )


def report_incident(
    db: Session, *, event_id: str, payload: RuntimeIncidentRequest
) -> RuntimeIncidentResponse:
    event = _get_event_or_error(db, event_id)
    reported_at = payload.reported_at or datetime.utcnow()

    incident = Incident(
        event_id=event.event_id,
        assignment_id=payload.assignment_id,
        incident_type=payload.incident_type,
        severity=payload.severity,
        reported_at=reported_at,
        reported_by=payload.reported_by,
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
        author_reference=payload.author_reference,
        timestamp_at=reported_at,
        message=payload.description,
        meta={
            "incident_type": payload.incident_type.value,
            "severity": payload.severity.value,
            "sla_impact": payload.sla_impact,
        },
    )
    db.add(log)
    db.commit()
    db.refresh(incident)
    db.refresh(log)
    return RuntimeIncidentResponse(
        event_id=event.event_id, incident_id=incident.incident_id, log_id=log.log_id
    )


def complete_event_execution(
    db: Session, *, event_id: str, payload: RuntimeCompleteRequest
) -> RuntimeCompleteResponse:
    event = _get_event_or_error(db, event_id)
    completed_at = payload.completed_at or datetime.utcnow()

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

    log = EventExecutionLog(
        event_id=event.event_id,
        log_type=OpsLogType.event_completed,
        author_type=payload.author_type,
        author_reference=payload.author_reference,
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
            timing.delay_minutes = int(
                (timing.actual_end - timing.planned_end).total_seconds() // 60
            )

    db.commit()
    db.refresh(outcome)
    db.refresh(log)
    db.refresh(timing)

    return RuntimeCompleteResponse(
        event_id=event.event_id,
        event_status=event.status.value,
        outcome_event_id=outcome.event_id,
        log_id=log.log_id,
        timing_id=timing.timing_id,
    )


def _get_event_or_error(db: Session, event_id: str) -> Event:
    event = db.get(Event, event_id)
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
