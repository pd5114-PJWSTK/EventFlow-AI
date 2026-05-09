from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EventAssignmentRead(BaseModel):
    assignment_id: str
    event_id: str
    resource_type: str
    person_id: str | None = None
    person_name: str | None = None
    equipment_id: str | None = None
    equipment_name: str | None = None
    vehicle_id: str | None = None
    vehicle_name: str | None = None
    assignment_role: str | None = None
    planned_start: datetime
    planned_end: datetime
    status: str
    is_consumed_in_execution: bool
    notes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class EventAssignmentListResponse(BaseModel):
    items: list[EventAssignmentRead]
    total: int
    limit: int
    offset: int
