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
