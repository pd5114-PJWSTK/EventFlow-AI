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
    SmallInteger,
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
AUTH_SCHEMA = None if settings.database_url.startswith("sqlite") else "auth"


def _ai_table(name: str) -> str:
    if AI_SCHEMA:
        return f"{AI_SCHEMA}.{name}"
    return name


def _core_table(name: str) -> str:
    if CORE_SCHEMA:
        return f"{CORE_SCHEMA}.{name}"
    return name


def _auth_table(name: str) -> str:
    if AUTH_SCHEMA:
        return f"{AUTH_SCHEMA}.{name}"
    return name


class PlannerRunStatus(str, Enum):
    started = "started"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class PredictionType(str, Enum):
    duration_estimate = "duration_estimate"
    required_headcount = "required_headcount"
    required_equipment_count = "required_equipment_count"
    delay_risk = "delay_risk"
    sla_breach_risk = "sla_breach_risk"
    incident_risk = "incident_risk"
    cost_estimate = "cost_estimate"
    recommended_buffer_minutes = "recommended_buffer_minutes"
    resource_reliability_score = "resource_reliability_score"
    fatigue_score = "fatigue_score"
    other = "other"


class ModelStatus(str, Enum):
    training = "training"
    active = "active"
    deprecated = "deprecated"
    archived = "archived"


class ModelRegistry(Base):
    __tablename__ = "models"
    __table_args__ = {"schema": AI_SCHEMA}

    model_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    model_version: Mapped[str] = mapped_column(Text, nullable=False)
    prediction_type: Mapped[PredictionType] = mapped_column(
        SAEnum(PredictionType, native_enum=False), nullable=False
    )
    status: Mapped[ModelStatus] = mapped_column(
        SAEnum(ModelStatus, native_enum=False),
        default=ModelStatus.training,
        nullable=False,
    )
    training_data_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    training_data_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metrics: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    predictions: Mapped[list[Prediction]] = relationship(back_populates="model")


class EventFeature(Base):
    __tablename__ = "event_features"
    __table_args__ = {"schema": AI_SCHEMA}

    event_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("events.event_id"), ondelete="CASCADE"),
        primary_key=True,
    )
    feature_event_type: Mapped[str | None] = mapped_column(Text)
    feature_event_subtype: Mapped[str | None] = mapped_column(Text)
    feature_city: Mapped[str | None] = mapped_column(Text)
    feature_location_type: Mapped[str | None] = mapped_column(Text)
    feature_attendee_count: Mapped[int | None] = mapped_column(Integer)
    feature_attendee_bucket: Mapped[str | None] = mapped_column(Text)
    feature_setup_complexity_score: Mapped[int | None] = mapped_column(SmallInteger)
    feature_access_difficulty: Mapped[int | None] = mapped_column(SmallInteger)
    feature_parking_difficulty: Mapped[int | None] = mapped_column(SmallInteger)
    feature_priority: Mapped[str | None] = mapped_column(Text)
    feature_day_of_week: Mapped[int | None] = mapped_column(SmallInteger)
    feature_month: Mapped[int | None] = mapped_column(SmallInteger)
    feature_season: Mapped[str | None] = mapped_column(Text)
    feature_requires_transport: Mapped[bool | None] = mapped_column(Boolean)
    feature_requires_setup: Mapped[bool | None] = mapped_column(Boolean)
    feature_requires_teardown: Mapped[bool | None] = mapped_column(Boolean)
    feature_required_person_count: Mapped[int | None] = mapped_column(Integer)
    feature_required_equipment_count: Mapped[int | None] = mapped_column(Integer)
    feature_required_vehicle_count: Mapped[int | None] = mapped_column(Integer)
    feature_estimated_distance_km: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2)
    )
    feature_client_priority: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

class ResourceFeature(Base):
    __tablename__ = "resource_features"
    __table_args__ = {"schema": AI_SCHEMA}

    resource_feature_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    resource_type: Mapped[AssignmentResourceType] = mapped_column(
        SAEnum(AssignmentResourceType, native_enum=False), nullable=False
    )
    person_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("resources_people.person_id"), ondelete="CASCADE"),
    )
    equipment_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("equipment.equipment_id"), ondelete="CASCADE"),
    )
    vehicle_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("vehicles.vehicle_id"), ondelete="CASCADE"),
    )
    avg_delay_last_10: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    avg_job_duration_variance: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    incident_rate_last_30d: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    utilization_rate_last_30d: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    fatigue_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    reliability_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = {"schema": AI_SCHEMA}

    prediction_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    event_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("events.event_id"), ondelete="CASCADE"),
    )
    assignment_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("assignments.assignment_id"), ondelete="SET NULL"),
    )
    model_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_ai_table("models.model_id"), ondelete="SET NULL"),
    )
    prediction_type: Mapped[PredictionType] = mapped_column(
        SAEnum(PredictionType, native_enum=False), nullable=False
    )
    predicted_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    predicted_label: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    explanation: Mapped[str | None] = mapped_column(Text)
    feature_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    model: Mapped[ModelRegistry | None] = relationship(back_populates="predictions")
    outcomes: Mapped[list[PredictionOutcome]] = relationship(
        back_populates="prediction",
        cascade="all,delete-orphan",
    )


class PredictionOutcome(Base):
    __tablename__ = "prediction_outcomes"
    __table_args__ = {"schema": AI_SCHEMA}

    prediction_outcome_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    prediction_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_ai_table("predictions.prediction_id"), ondelete="CASCADE"),
        nullable=False,
    )
    actual_numeric_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    actual_label: Mapped[str | None] = mapped_column(Text)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    error_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    notes: Mapped[str | None] = mapped_column(Text)

    prediction: Mapped[Prediction] = relationship(back_populates="outcomes")


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
    initiated_by_user_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_auth_table("users.user_id"), ondelete="SET NULL"),
    )
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
