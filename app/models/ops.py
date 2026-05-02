from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.config import get_settings
from app.database import Base
from app.models.core import AssignmentResourceType


settings = get_settings()
CORE_SCHEMA = None if settings.database_url.startswith("sqlite") else "core"
OPS_SCHEMA = None if settings.database_url.startswith("sqlite") else "ops"


def _core_table(name: str) -> str:
    if CORE_SCHEMA:
        return f"{CORE_SCHEMA}.{name}"
    return name


def _ops_table(name: str) -> str:
    if OPS_SCHEMA:
        return f"{OPS_SCHEMA}.{name}"
    return name


class OpsLogType(str, Enum):
    event_created = "event_created"
    planning_started = "planning_started"
    planning_completed = "planning_completed"
    resource_assigned = "resource_assigned"
    resource_unassigned = "resource_unassigned"
    transport_started = "transport_started"
    transport_arrived = "transport_arrived"
    setup_started = "setup_started"
    setup_completed = "setup_completed"
    event_started = "event_started"
    event_completed = "event_completed"
    teardown_started = "teardown_started"
    teardown_completed = "teardown_completed"
    delay_reported = "delay_reported"
    incident_reported = "incident_reported"
    status_changed = "status_changed"
    manual_override = "manual_override"
    note = "note"


class OpsAuthorType(str, Enum):
    system = "system"
    planner = "planner"
    coordinator = "coordinator"
    technician = "technician"
    manager = "manager"
    client = "client"
    other = "other"


class OpsPhaseName(str, Enum):
    loadout = "loadout"
    transport_outbound = "transport_outbound"
    setup = "setup"
    soundcheck = "soundcheck"
    event_runtime = "event_runtime"
    teardown = "teardown"
    transport_return = "transport_return"
    other = "other"


class OpsIncidentType(str, Enum):
    delay = "delay"
    equipment_failure = "equipment_failure"
    staff_absence = "staff_absence"
    traffic_issue = "traffic_issue"
    weather_issue = "weather_issue"
    client_change_request = "client_change_request"
    venue_access_issue = "venue_access_issue"
    sla_risk = "sla_risk"
    safety_issue = "safety_issue"
    other = "other"


class OpsIncidentSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class IdempotencyStatus(str, Enum):
    processing = "processing"
    completed = "completed"
    failed = "failed"


class EventExecutionLog(Base):
    __tablename__ = "event_execution_logs"
    __table_args__ = {"schema": OPS_SCHEMA}

    log_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    event_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("events.event_id"), ondelete="CASCADE"),
        nullable=False,
    )
    assignment_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("assignments.assignment_id"), ondelete="SET NULL"),
    )
    timestamp_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    log_type: Mapped[OpsLogType] = mapped_column(
        SAEnum(OpsLogType, native_enum=False), nullable=False
    )
    author_type: Mapped[OpsAuthorType] = mapped_column(
        SAEnum(OpsAuthorType, native_enum=False),
        default=OpsAuthorType.system,
        nullable=False,
    )
    author_reference: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ActualTiming(Base):
    __tablename__ = "actual_timings"
    __table_args__ = {"schema": OPS_SCHEMA}

    timing_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    event_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("events.event_id"), ondelete="CASCADE"),
        nullable=False,
    )
    assignment_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("assignments.assignment_id"), ondelete="SET NULL"),
    )
    phase_name: Mapped[OpsPhaseName] = mapped_column(
        SAEnum(OpsPhaseName, native_enum=False), nullable=False
    )
    planned_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    planned_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delay_minutes: Mapped[int | None] = mapped_column(Integer)
    delay_reason_code: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = {"schema": OPS_SCHEMA}

    incident_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    event_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("events.event_id"), ondelete="CASCADE"),
        nullable=False,
    )
    assignment_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("assignments.assignment_id"), ondelete="SET NULL"),
    )
    incident_type: Mapped[OpsIncidentType] = mapped_column(
        SAEnum(OpsIncidentType, native_enum=False), nullable=False
    )
    severity: Mapped[OpsIncidentSeverity] = mapped_column(
        SAEnum(OpsIncidentSeverity, native_enum=False),
        default=OpsIncidentSeverity.medium,
        nullable=False,
    )
    reported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reported_by: Mapped[str | None] = mapped_column(Text)
    root_cause: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    cost_impact: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    sla_impact: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class EventOutcome(Base):
    __tablename__ = "event_outcomes"
    __table_args__ = {"schema": OPS_SCHEMA}

    event_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("events.event_id"), ondelete="CASCADE"),
        primary_key=True,
    )
    finished_on_time: Mapped[bool | None] = mapped_column(Boolean)
    total_delay_minutes: Mapped[int | None] = mapped_column(Integer)
    actual_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    overtime_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    transport_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    sla_breached: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    client_satisfaction_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    internal_quality_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    margin_estimate: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    summary_notes: Mapped[str | None] = mapped_column(Text)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class ResourceCheckpoint(Base):
    __tablename__ = "resource_checkpoints"
    __table_args__ = {"schema": OPS_SCHEMA}

    checkpoint_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    event_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("events.event_id"), ondelete="CASCADE"),
        nullable=False,
    )
    assignment_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("assignments.assignment_id"), ondelete="SET NULL"),
    )
    resource_type: Mapped[AssignmentResourceType] = mapped_column(
        SAEnum(AssignmentResourceType, native_enum=False), nullable=False
    )
    person_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("resources_people.person_id"), ondelete="SET NULL"),
    )
    equipment_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("equipment.equipment_id"), ondelete="SET NULL"),
    )
    vehicle_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("vehicles.vehicle_id"), ondelete="SET NULL"),
    )
    checkpoint_type: Mapped[str] = mapped_column(Text, nullable=False)
    checkpoint_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    notes: Mapped[str | None] = mapped_column(Text)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("scope", "idempotency_key", name="uq_idempotency_scope_key"),
        {"schema": OPS_SCHEMA},
    )

    idempotency_record_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    event_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("events.event_id"), ondelete="SET NULL"),
    )
    request_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[IdempotencyStatus] = mapped_column(
        SAEnum(IdempotencyStatus, native_enum=False),
        default=IdempotencyStatus.processing,
        nullable=False,
    )
    response_payload: Mapped[dict | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
