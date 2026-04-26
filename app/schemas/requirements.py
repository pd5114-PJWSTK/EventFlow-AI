from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.core import PersonRole, RequirementType, VehicleType


class EventRequirementCreate(BaseModel):
    requirement_type: RequirementType
    role_required: PersonRole | None = None
    skill_id: str | None = None
    equipment_type_id: str | None = None
    vehicle_type_required: VehicleType | None = None
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    mandatory: bool = True
    required_start: datetime | None = None
    required_end: datetime | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_coherence(self) -> "EventRequirementCreate":
        if self.required_start and self.required_end and self.required_end <= self.required_start:
            raise ValueError("required_end must be after required_start")

        if self.requirement_type == RequirementType.person_role and self.role_required is None:
            raise ValueError("role_required is required for person_role")
        if self.requirement_type == RequirementType.person_skill and self.skill_id is None:
            raise ValueError("skill_id is required for person_skill")
        if self.requirement_type == RequirementType.equipment_type and self.equipment_type_id is None:
            raise ValueError("equipment_type_id is required for equipment_type")
        if self.requirement_type == RequirementType.vehicle_type and self.vehicle_type_required is None:
            raise ValueError("vehicle_type_required is required for vehicle_type")
        return self


class EventRequirementUpdate(BaseModel):
    requirement_type: RequirementType | None = None
    role_required: PersonRole | None = None
    skill_id: str | None = None
    equipment_type_id: str | None = None
    vehicle_type_required: VehicleType | None = None
    quantity: Decimal | None = Field(default=None, gt=0)
    mandatory: bool | None = None
    required_start: datetime | None = None
    required_end: datetime | None = None
    notes: str | None = None


class EventRequirementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    requirement_id: str
    event_id: str
    requirement_type: RequirementType
    role_required: PersonRole | None
    skill_id: str | None
    equipment_type_id: str | None
    vehicle_type_required: VehicleType | None
    quantity: Decimal
    mandatory: bool
    required_start: datetime | None
    required_end: datetime | None
    notes: str | None
    created_at: datetime


class EventRequirementListResponse(BaseModel):
    items: list[EventRequirementRead]
    total: int
    limit: int
    offset: int
