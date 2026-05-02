from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ConstraintCheckRequest(BaseModel):
    event_id: str


class ConstraintGap(BaseModel):
    code: str
    requirement_id: str | None = None
    message: str
    severity: Literal["critical", "warning"] = "critical"


class ConstraintCostBreakdown(BaseModel):
    people_cost: Decimal = Field(default=Decimal("0.00"))
    equipment_cost: Decimal = Field(default=Decimal("0.00"))
    vehicles_cost: Decimal = Field(default=Decimal("0.00"))
    total_cost: Decimal = Field(default=Decimal("0.00"))


class ConstraintCheckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    checked_at: datetime
    is_supportable: bool
    gaps: list[ConstraintGap] = Field(default_factory=list)
    supportable_requirements: list[str] = Field(default_factory=list)
    unsupported_requirements: list[str] = Field(default_factory=list)
    estimated_cost: Decimal = Field(default=Decimal("0.00"))
    cost_breakdown: ConstraintCostBreakdown = Field(
        default_factory=ConstraintCostBreakdown
    )
    budget_available: Decimal | None = None
    budget_exceeded: bool = False


class GeneratePlanRequest(BaseModel):
    event_id: str
    initiated_by: str | None = None
    trigger_reason: str = "manual"
    commit_to_assignments: bool = True
    solver_timeout_seconds: float = Field(default=10.0, gt=0, le=30.0)
    fallback_enabled: bool = True


class GeneratedPlanAssignment(BaseModel):
    requirement_id: str
    resource_type: str
    resource_ids: list[str] = Field(default_factory=list)
    unassigned_count: int
    estimated_cost: Decimal = Field(default=Decimal("0.00"))


class GeneratePlanResponse(BaseModel):
    event_id: str
    planner_run_id: str
    recommendation_id: str
    plan_id: str
    solver: Literal["ortools", "fallback"]
    solver_duration_ms: int = 0
    fallback_reason: str | None = None
    fallback_enabled: bool = True
    solver_timeout_seconds: float
    is_fully_assigned: bool
    assignments: list[GeneratedPlanAssignment] = Field(default_factory=list)
    assignment_ids: list[str] = Field(default_factory=list)
    transport_leg_ids: list[str] = Field(default_factory=list)
    estimated_cost: Decimal = Field(default=Decimal("0.00"))


class ReplanRequest(BaseModel):
    incident_id: str | None = None
    incident_summary: str | None = None
    initiated_by: str | None = None
    commit_to_assignments: bool = True
    solver_timeout_seconds: float = Field(default=10.0, gt=0, le=30.0)
    fallback_enabled: bool = True
    preserve_consumed_resources: bool = True


class PlanMetricComparison(BaseModel):
    previous_cost: Decimal | None = None
    new_cost: Decimal
    cost_delta: Decimal | None = None
    previous_duration_minutes: int | None = None
    new_duration_minutes: int | None = None
    duration_delta_minutes: int | None = None
    previous_risk: Decimal | None = None
    new_risk: Decimal | None = None
    risk_delta: Decimal | None = None
    is_improved: bool | None = None
    decision_note: str


class ReplanResponse(BaseModel):
    event_id: str
    planner_run_id: str
    planner_run_trigger_reason: str
    recommendation_id: str
    baseline_recommendation_id: str | None = None
    incident_id: str | None = None
    incident_summary: str | None = None
    comparison: PlanMetricComparison
    generated_plan: GeneratePlanResponse


class PlanCandidateEvaluation(BaseModel):
    candidate_name: str
    solver: str
    estimated_cost: Decimal
    predicted_transport_duration_minutes: Decimal
    predicted_setup_duration_minutes: Decimal
    predicted_teardown_duration_minutes: Decimal
    estimated_duration_minutes: Decimal
    predicted_delay_risk: Decimal
    predicted_incident_risk: Decimal
    predicted_sla_breach_risk: Decimal
    coverage_ratio: Decimal
    unassigned_count: int
    confidence_score: Decimal
    ood_score: Decimal
    guardrail_applied: bool = False
    guardrail_reason: str | None = None
    plan_score: Decimal
    selection_explanation: str
    profile_weights: dict[str, Decimal] = Field(default_factory=dict)


class RecommendBestPlanRequest(BaseModel):
    event_id: str
    initiated_by: str | None = None
    commit_to_assignments: bool = False
    solver_timeout_seconds: float = Field(default=10.0, gt=0, le=30.0)
    fallback_enabled: bool = True
    duration_model_id: str | None = None
    plan_evaluator_model_id: str | None = None


class RecommendBestPlanResponse(BaseModel):
    event_id: str
    planner_run_id: str
    recommendation_id: str
    selected_candidate_name: str
    selected_plan_score: Decimal
    selected_explanation: str
    selected_plan: GeneratePlanResponse
    candidates: list[PlanCandidateEvaluation] = Field(default_factory=list)
