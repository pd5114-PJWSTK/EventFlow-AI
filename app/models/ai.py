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
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.database import Base
from app.models.core import AssignmentResourceType


settings = get_settings()
AI_SCHEMA = None if settings.database_url.startswith("sqlite") else "ai"
CORE_SCHEMA = None if settings.database_url.startswith("sqlite") else "core"


def _ai_table(name: str) -> str:
    if AI_SCHEMA:
        return f"{AI_SCHEMA}.{name}"
    return name


def _core_table(name: str) -> str:
    if CORE_SCHEMA:
        return f"{CORE_SCHEMA}.{name}"
    return name


class PlannerRunStatus(str, Enum):
    started = "started"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class PlannerRun(Base):
    __tablename__ = "planner_runs"
    __table_args__ = {"schema": AI_SCHEMA}

    planner_run_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    run_status: Mapped[PlannerRunStatus] = mapped_column(
        SAEnum(PlannerRunStatus, native_enum=False),
        default=PlannerRunStatus.started,
        nullable=False,
    )
    objective_version: Mapped[str | None] = mapped_column(Text)
    initiated_by: Mapped[str | None] = mapped_column(Text)
    trigger_reason: Mapped[str | None] = mapped_column(Text)
    input_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    total_risk_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    sla_risk_count: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)

    recommendations: Mapped[list[PlannerRecommendation]] = relationship(
        back_populates="planner_run",
        cascade="all,delete-orphan",
    )


class PlannerRecommendation(Base):
    __tablename__ = "planner_recommendations"
    __table_args__ = {"schema": AI_SCHEMA}

    recommendation_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    planner_run_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_ai_table("planner_runs.planner_run_id"), ondelete="CASCADE"),
        nullable=False,
    )
    event_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("events.event_id"), ondelete="CASCADE"),
        nullable=False,
    )
    expected_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    expected_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    expected_risk: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    selected_for_execution: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    rationale: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    planner_run: Mapped[PlannerRun] = relationship(back_populates="recommendations")
    assignment_details: Mapped[list[PlannerRecommendationAssignment]] = relationship(
        back_populates="recommendation",
        cascade="all,delete-orphan",
    )


class PlannerRecommendationAssignment(Base):
    __tablename__ = "planner_recommendation_assignments"
    __table_args__ = {"schema": AI_SCHEMA}

    recommendation_assignment_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    recommendation_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(
            _ai_table("planner_recommendations.recommendation_id"),
            ondelete="CASCADE",
        ),
        nullable=False,
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
    assignment_role: Mapped[str | None] = mapped_column(Text)
    planned_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    planned_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    risk_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    cost_estimate: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    recommendation: Mapped[PlannerRecommendation] = relationship(
        back_populates="assignment_details"
    )
