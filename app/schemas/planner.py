from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.core import PersonRole, VehicleType


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


class RequirementGapSummary(BaseModel):
    requirement_id: str
    resource_type: str
    missing_count: int
    message: str


class GapResolutionOption(BaseModel):
    option_type: Literal["augment_resources", "reschedule_event"]
    title: str
    description: str
    steps: list[str] = Field(default_factory=list)
    endpoints: list[str] = Field(default_factory=list)


class SuggestedRescheduleWindow(BaseModel):
    planned_start: datetime
    planned_end: datetime
    score: Decimal = Field(default=Decimal("0.00"))
    note: str


class GapResolutionGuidance(BaseModel):
    has_gaps: bool = False
    requirement_gaps: list[RequirementGapSummary] = Field(default_factory=list)
    options: list[GapResolutionOption] = Field(default_factory=list)
    suggested_reschedule_windows: list[SuggestedRescheduleWindow] = Field(
        default_factory=list
    )


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
    gap_resolution: GapResolutionGuidance | None = None


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


class ReplanOperatorAction(BaseModel):
    action_type: Literal["add_resource", "swap_resource", "shift_timing", "manual_note"]
    label: str = Field(min_length=1, max_length=500)
    owner: str = Field(min_length=1, max_length=120)
    status: Literal["pending", "done"] = "pending"
    resource_type: Literal["person", "equipment", "vehicle"] | None = None
    resource_id: str | None = None
    timing_delta_minutes: int | None = None

    @model_validator(mode="after")
    def validate_action_payload(self) -> "ReplanOperatorAction":
        if self.action_type in {"add_resource", "swap_resource"}:
            if not self.resource_type or not self.resource_id:
                raise ValueError("resource actions require resource_type and resource_id")
        if self.action_type == "shift_timing" and self.timing_delta_minutes is None:
            raise ValueError("shift_timing requires timing_delta_minutes")
        return self


class ReplanRequest(BaseModel):
    incident_id: str | None = None
    incident_summary: str | None = None
    operator_actions: list[ReplanOperatorAction] = Field(default_factory=list)
    initiated_by: str | None = None
    commit_to_assignments: bool = True
    solver_timeout_seconds: float = Field(default=10.0, gt=0, le=30.0)
    fallback_enabled: bool = True
    preserve_consumed_resources: bool = True
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)
    expected_event_updated_at: datetime | None = None


class ReplanResponse(BaseModel):
    event_id: str
    planner_run_id: str
    planner_run_trigger_reason: str
    recommendation_id: str
    baseline_recommendation_id: str | None = None
    incident_id: str | None = None
    incident_summary: str | None = None
    operator_actions: list[ReplanOperatorAction] = Field(default_factory=list)
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


class AssignmentOverride(BaseModel):
    requirement_id: str
    resource_type: Literal["person", "equipment", "vehicle"]
    resource_ids: list[str] = Field(default_factory=list)


class RecommendBestPlanRequest(BaseModel):
    event_id: str
    initiated_by: str | None = None
    commit_to_assignments: bool = False
    solver_timeout_seconds: float = Field(default=10.0, gt=0, le=30.0)
    fallback_enabled: bool = True
    duration_model_id: str | None = None
    plan_evaluator_model_id: str | None = None
    assignment_overrides: list[AssignmentOverride] = Field(default_factory=list)


class RecommendBestPlanResponse(BaseModel):
    event_id: str
    planner_run_id: str
    recommendation_id: str
    selected_candidate_name: str
    selected_plan_score: Decimal
    selected_explanation: str
    selected_plan: GeneratePlanResponse
    candidates: list[PlanCandidateEvaluation] = Field(default_factory=list)


class GapAugmentPersonInput(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    role: PersonRole
    home_base_location_id: str | None = None
    cost_per_hour: Decimal | None = None
    reliability_notes: str | None = None
    available_from: datetime | None = None
    available_to: datetime | None = None


class GapAugmentEquipmentInput(BaseModel):
    equipment_type_id: str
    asset_tag: str | None = None
    warehouse_location_id: str | None = None
    hourly_cost_estimate: Decimal | None = None
    transport_requirements: str | None = None
    available_from: datetime | None = None
    available_to: datetime | None = None


class GapAugmentVehicleInput(BaseModel):
    vehicle_name: str = Field(min_length=1, max_length=255)
    vehicle_type: VehicleType
    home_location_id: str | None = None
    registration_number: str | None = None
    cost_per_km: Decimal | None = None
    cost_per_hour: Decimal | None = None
    available_from: datetime | None = None
    available_to: datetime | None = None


class ResolvePlanGapsRequest(BaseModel):
    strategy: Literal["augment_resources", "reschedule_event"]
    initiated_by: str | None = None
    commit_to_assignments: bool = True
    solver_timeout_seconds: float = Field(default=10.0, gt=0, le=30.0)
    fallback_enabled: bool = True
    add_people: list[GapAugmentPersonInput] = Field(default_factory=list)
    add_equipment: list[GapAugmentEquipmentInput] = Field(default_factory=list)
    add_vehicles: list[GapAugmentVehicleInput] = Field(default_factory=list)
    new_planned_start: datetime | None = None
    new_planned_end: datetime | None = None
    expected_event_updated_at: datetime | None = None
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_strategy_payload(self) -> "ResolvePlanGapsRequest":
        if self.strategy == "augment_resources":
            if not (self.add_people or self.add_equipment or self.add_vehicles):
                raise ValueError(
                    "augment_resources requires add_people/add_equipment/add_vehicles."
                )
        if self.strategy == "reschedule_event":
            if self.new_planned_start is None or self.new_planned_end is None:
                raise ValueError(
                    "reschedule_event requires new_planned_start and new_planned_end."
                )
            if self.new_planned_end <= self.new_planned_start:
                raise ValueError("new_planned_end must be after new_planned_start.")
        return self


class ResolvePlanGapsResponse(BaseModel):
    event_id: str
    strategy: Literal["augment_resources", "reschedule_event"]
    created_people_ids: list[str] = Field(default_factory=list)
    created_equipment_ids: list[str] = Field(default_factory=list)
    created_vehicle_ids: list[str] = Field(default_factory=list)
    updated_event_window_start: datetime | None = None
    updated_event_window_end: datetime | None = None
    generated_plan: GeneratePlanResponse
    decision_summary: str


class GapResolutionPreviewResponse(BaseModel):
    event_id: str
    preview_generated_at: datetime
    contract_version: str = "cp03.v1"
    generated_plan: GeneratePlanResponse


class GapResolutionPreviewRequest(BaseModel):
    initiated_by: str | None = None
    solver_timeout_seconds: float = Field(default=10.0, gt=0, le=30.0)
    fallback_enabled: bool = True
