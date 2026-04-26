from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator


class AvailabilityCreate(BaseModel):
    available_from: datetime
    available_to: datetime
    is_available: bool = True
    source: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_window(self) -> "AvailabilityCreate":
        if self.available_to <= self.available_from:
            raise ValueError("available_to must be after available_from")
        return self


class AvailabilityUpdate(BaseModel):
    available_from: datetime | None = None
    available_to: datetime | None = None
    is_available: bool | None = None
    source: str | None = None
    notes: str | None = None


class PeopleAvailabilityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    availability_id: str
    person_id: str
    available_from: datetime
    available_to: datetime
    is_available: bool
    source: str | None
    notes: str | None
    created_at: datetime


class EquipmentAvailabilityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    availability_id: str
    equipment_id: str
    available_from: datetime
    available_to: datetime
    is_available: bool
    source: str | None
    notes: str | None
    created_at: datetime


class VehicleAvailabilityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    availability_id: str
    vehicle_id: str
    available_from: datetime
    available_to: datetime
    is_available: bool
    source: str | None
    notes: str | None
    created_at: datetime


class PeopleAvailabilityListResponse(BaseModel):
    items: list[PeopleAvailabilityRead]
    total: int
    limit: int
    offset: int


class EquipmentAvailabilityListResponse(BaseModel):
    items: list[EquipmentAvailabilityRead]
    total: int
    limit: int
    offset: int


class VehicleAvailabilityListResponse(BaseModel):
    items: list[VehicleAvailabilityRead]
    total: int
    limit: int
    offset: int
