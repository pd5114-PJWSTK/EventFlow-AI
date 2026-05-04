from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.core import EventStatus, PriorityLevel


def _validate_business_text(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be empty")
    if not any(char.isalpha() for char in stripped):
        raise ValueError(f"{field_name} must contain letters")
    return stripped


class EventCreate(BaseModel):
    client_id: str
    location_id: str
    event_name: str = Field(min_length=1, max_length=255)
    event_type: str = Field(min_length=1, max_length=128)
    event_subtype: str | None = None
    description: str | None = None
    attendee_count: int | None = Field(default=None, ge=0)
    planned_start: datetime
    planned_end: datetime
    priority: PriorityLevel = PriorityLevel.medium
    status: EventStatus = EventStatus.draft
    budget_estimate: Decimal | None = None
    currency_code: str = Field(default="PLN", min_length=3, max_length=3)
    source_channel: str | None = None
    requires_transport: bool = True
    requires_setup: bool = True
    requires_teardown: bool = True
    notes: str | None = None
    created_by: str | None = None
    created_by_user_id: str | None = None

    @field_validator("event_name", "event_type")
    @classmethod
    def validate_text_fields(cls, value: str, info) -> str:
        result = _validate_business_text(value, info.field_name)
        if result is None:
            raise ValueError(f"{info.field_name} must not be empty")
        return result

    @model_validator(mode="after")
    def validate_time_range(self) -> "EventCreate":
        if self.planned_end <= self.planned_start:
            raise ValueError("planned_end must be after planned_start")
        return self


class EventUpdate(BaseModel):
    client_id: str | None = None
    location_id: str | None = None
    event_name: str | None = Field(default=None, min_length=1, max_length=255)
    event_type: str | None = Field(default=None, min_length=1, max_length=128)
    event_subtype: str | None = None
    description: str | None = None
    attendee_count: int | None = Field(default=None, ge=0)
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    priority: PriorityLevel | None = None
    status: EventStatus | None = None
    budget_estimate: Decimal | None = None
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    source_channel: str | None = None
    requires_transport: bool | None = None
    requires_setup: bool | None = None
    requires_teardown: bool | None = None
    notes: str | None = None
    created_by: str | None = None
    created_by_user_id: str | None = None

    @field_validator("event_name", "event_type")
    @classmethod
    def validate_text_fields(cls, value: str | None, info) -> str | None:
        return _validate_business_text(value, info.field_name)

    @model_validator(mode="after")
    def validate_time_range(self) -> "EventUpdate":
        if self.planned_start and self.planned_end and self.planned_end <= self.planned_start:
            raise ValueError("planned_end must be after planned_start")
        return self


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    client_id: str
    location_id: str
    event_name: str
    event_type: str
    event_subtype: str | None
    description: str | None
    attendee_count: int | None
    planned_start: datetime
    planned_end: datetime
    priority: PriorityLevel
    status: EventStatus
    budget_estimate: Decimal | None
    currency_code: str
    source_channel: str | None
    requires_transport: bool
    requires_setup: bool
    requires_teardown: bool
    notes: str | None
    created_by: str | None
    created_by_user_id: str | None
    created_at: datetime
    updated_at: datetime


class EventListResponse(BaseModel):
    items: list[EventRead]
    total: int
    limit: int
    offset: int
