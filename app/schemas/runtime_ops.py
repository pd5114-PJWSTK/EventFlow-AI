from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.core import AssignmentResourceType
from app.models.ops import (
    OpsAuthorType,
    OpsIncidentSeverity,
    OpsIncidentType,
    OpsPhaseName,
)


class RuntimeStartRequest(BaseModel):
    started_at: datetime | None = None
    author_type: OpsAuthorType = OpsAuthorType.system
    author_reference: str | None = None
    message: str | None = None
    phase_name: OpsPhaseName = OpsPhaseName.event_runtime
    delay_reason_code: str | None = None
    notes: str | None = None
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)


class RuntimeStartResponse(BaseModel):
    event_id: str
    event_status: str
    log_id: str
    timing_id: str


class RuntimeCheckpointRequest(BaseModel):
    assignment_id: str | None = None
    resource_type: AssignmentResourceType
    person_id: str | None = None
    equipment_id: str | None = None
    vehicle_id: str | None = None
    checkpoint_type: str = Field(min_length=1, max_length=120)
    checkpoint_time: datetime | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    notes: str | None = None
    author_type: OpsAuthorType = OpsAuthorType.system
    author_reference: str | None = None
    message: str | None = None
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_resource_identity(self) -> "RuntimeCheckpointRequest":
        if self.resource_type == AssignmentResourceType.person:
            if self.person_id is None or self.equipment_id is not None or self.vehicle_id is not None:
                raise ValueError("For person checkpoint provide only person_id.")
        elif self.resource_type == AssignmentResourceType.equipment:
            if self.equipment_id is None or self.person_id is not None or self.vehicle_id is not None:
                raise ValueError("For equipment checkpoint provide only equipment_id.")
        elif self.resource_type == AssignmentResourceType.vehicle:
            if self.vehicle_id is None or self.person_id is not None or self.equipment_id is not None:
                raise ValueError("For vehicle checkpoint provide only vehicle_id.")
        return self


class RuntimeCheckpointResponse(BaseModel):
    event_id: str
    checkpoint_id: str
    log_id: str


class RuntimeIncidentRequest(BaseModel):
    assignment_id: str | None = None
    incident_type: OpsIncidentType
    severity: OpsIncidentSeverity = OpsIncidentSeverity.medium
    reported_at: datetime | None = None
    reported_by: str | None = None
    root_cause: str | None = None
    description: str = Field(min_length=1, max_length=4000)
    cost_impact: Decimal | None = None
    sla_impact: bool = False
    author_type: OpsAuthorType = OpsAuthorType.system
    author_reference: str | None = None
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)


class RuntimeIncidentResponse(BaseModel):
    event_id: str
    incident_id: str
    log_id: str


class RuntimeIncidentParseRequest(BaseModel):
    raw_log: str = Field(min_length=1, max_length=4000)
    assignment_id: str | None = None
    reported_at: datetime | None = None
    reported_by: str | None = None
    author_type: OpsAuthorType = OpsAuthorType.system
    author_reference: str | None = None
    prefer_llm: bool = True
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)


class RuntimeIncidentParseResponse(BaseModel):
    event_id: str
    incident_id: str
    log_id: str
    incident_type: str
    severity: str
    description: str
    root_cause: str | None = None
    sla_impact: bool
    cost_impact: Decimal | None = None
    reported_by: str | None = None
    parser_mode: str
    parse_confidence: float


class RuntimeCompleteRequest(BaseModel):
    completed_at: datetime | None = None
    finished_on_time: bool | None = None
    total_delay_minutes: int | None = None
    actual_cost: Decimal | None = None
    overtime_cost: Decimal | None = None
    transport_cost: Decimal | None = None
    sla_breached: bool = False
    client_satisfaction_score: Decimal | None = None
    internal_quality_score: Decimal | None = None
    margin_estimate: Decimal | None = None
    summary_notes: str | None = None
    author_type: OpsAuthorType = OpsAuthorType.system
    author_reference: str | None = None
    message: str | None = None
    phase_name: OpsPhaseName = OpsPhaseName.event_runtime
    delay_reason_code: str | None = None
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)


class RuntimeCompleteResponse(BaseModel):
    event_id: str
    event_status: str
    outcome_event_id: str
    log_id: str
    timing_id: str


class RuntimeNotificationItem(BaseModel):
    event_id: str
    notification_type: str
    payload: dict = Field(default_factory=dict)
    emitted_at: str


class RuntimeNotificationFeedResponse(BaseModel):
    event_id: str
    items: list[RuntimeNotificationItem] = Field(default_factory=list)
    total: int


class RuntimePostEventParseRequest(BaseModel):
    raw_summary: str = Field(min_length=1, max_length=6000)
    prefer_llm: bool = True
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)


class RuntimePostEventParseResponse(BaseModel):
    event_id: str
    parser_mode: str
    parse_confidence: float
    gaps: list[str] = Field(default_factory=list)
    draft_complete: RuntimeCompleteRequest


class RuntimePostEventCommitRequest(BaseModel):
    completion: RuntimeCompleteRequest
    source_mode: str = "manual"
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)


class RuntimePostEventCommitResponse(BaseModel):
    event_id: str
    source_mode: str
    committed_at: datetime
    completion: RuntimeCompleteResponse
