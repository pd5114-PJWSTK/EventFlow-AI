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
    is_fully_assigned: bool
    assignments: list[GeneratedPlanAssignment] = Field(default_factory=list)
    assignment_ids: list[str] = Field(default_factory=list)
    transport_leg_ids: list[str] = Field(default_factory=list)
    estimated_cost: Decimal = Field(default=Decimal("0.00"))
