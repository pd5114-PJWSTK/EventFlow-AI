from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.models.core import LocationType, PersonRole, PriorityLevel, RequirementType, VehicleType


class AIParsedRequirement(BaseModel):
    requirement_type: str
    quantity: int
    notes: str | None = None


class AIParsedInput(BaseModel):
    event_name: str | None = None
    requirements: list[AIParsedRequirement] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class AIOptimization(BaseModel):
    summary: str
    changes: list[str] = Field(default_factory=list)
    tradeoffs: list[str] = Field(default_factory=list)


class AIRiskEvaluation(BaseModel):
    overall_risk: str
    top_risks: list[str] = Field(default_factory=list)
    mitigations: list[str] = Field(default_factory=list)


class AIAgentsOptimizeRequest(BaseModel):
    raw_input: str = Field(min_length=1, max_length=6000)
    planner_snapshot: str = Field(default="", max_length=12000)
    prefer_langgraph: bool = True


class AIAgentsOptimizeResponse(BaseModel):
    parsed_input: AIParsedInput
    optimization: AIOptimization
    used_fallback: bool
    fallback_steps: list[str] = Field(default_factory=list)
    execution_mode: str


class AIAgentsEvaluateRequest(BaseModel):
    raw_input: str = Field(default="", max_length=6000)
    planner_snapshot: str = Field(default="", max_length=12000)
    plan_summary: str = Field(min_length=1, max_length=12000)
    prefer_langgraph: bool = True


class AIAgentsEvaluateResponse(BaseModel):
    parsed_input: AIParsedInput
    optimization: AIOptimization
    evaluation: AIRiskEvaluation
    used_fallback: bool
    fallback_steps: list[str] = Field(default_factory=list)
    execution_mode: str


class AIAgentsIngestEventRequest(BaseModel):
    raw_input: str = Field(min_length=1, max_length=12000)
    initiated_by: str | None = None
    prefer_langgraph: bool = True


class AIAgentsIngestEventDraftGap(BaseModel):
    field: str
    message: str
    severity: Literal["critical", "warning"] = "warning"


class AIAgentsIngestEventDraftRequirement(BaseModel):
    requirement_type: RequirementType
    role_required: PersonRole | None = None
    skill_id: str | None = None
    equipment_type_id: str | None = None
    vehicle_type_required: VehicleType | None = None
    quantity: Decimal = Field(default=Decimal("1"))
    mandatory: bool = True
    notes: str | None = None


class AIAgentsIngestEventDraftPayload(BaseModel):
    client_id: str | None = None
    client_name: str = Field(min_length=1, max_length=255)
    client_priority: PriorityLevel = PriorityLevel.medium
    location_id: str | None = None
    location_name: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=255)
    location_type: LocationType = LocationType.conference_center
    setup_complexity_score: int = Field(default=6, ge=1, le=10)
    access_difficulty: int = Field(default=3, ge=1, le=5)
    parking_difficulty: int = Field(default=3, ge=1, le=5)
    event_name: str = Field(min_length=1, max_length=255)
    event_type: str = Field(min_length=1, max_length=128)
    event_subtype: str | None = None
    attendee_count: int = Field(default=0, ge=0)
    planned_start: datetime
    planned_end: datetime
    event_priority: PriorityLevel = PriorityLevel.medium
    budget_estimate: Decimal = Field(default=Decimal("0.00"))
    requires_transport: bool = True
    requires_setup: bool = True
    requires_teardown: bool = True
    requirements: list[AIAgentsIngestEventDraftRequirement] = Field(default_factory=list)


class AIAgentsIngestEventPreviewRequest(BaseModel):
    raw_input: str = Field(min_length=1, max_length=12000)
    initiated_by: str | None = None
    prefer_langgraph: bool = True


class AIAgentsIngestEventPreviewResponse(BaseModel):
    draft: AIAgentsIngestEventDraftPayload
    assumptions: list[str] = Field(default_factory=list)
    gaps: list[AIAgentsIngestEventDraftGap] = Field(default_factory=list)
    parser_mode: str
    used_fallback: bool


class AIAgentsIngestEventCommitRequest(BaseModel):
    draft: AIAgentsIngestEventDraftPayload
    assumptions: list[str] = Field(default_factory=list)
    parser_mode: str = "manual_commit"
    used_fallback: bool = False
    initiated_by: str | None = None


class AIAgentsIngestEventResponse(BaseModel):
    client_id: str
    location_id: str
    event_id: str
    requirement_ids: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    parser_mode: str
    used_fallback: bool
