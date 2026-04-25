from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.core import PriorityLevel


class ClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    industry: str | None = None
    priority: PriorityLevel = PriorityLevel.medium
    sla_type: str | None = None
    contact_person_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    notes: str | None = None


class ClientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    industry: str | None = None
    priority: PriorityLevel | None = None
    sla_type: str | None = None
    contact_person_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    notes: str | None = None


class ClientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    client_id: str
    name: str
    industry: str | None
    priority: PriorityLevel
    sla_type: str | None
    contact_person_name: str | None
    contact_email: str | None
    contact_phone: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ClientListResponse(BaseModel):
    items: list[ClientRead]
    total: int
    limit: int
    offset: int
