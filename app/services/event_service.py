from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.core import Client, Event, EventStatus, Location
from app.schemas.events import EventCreate, EventUpdate


ALLOWED_STATUS_TRANSITIONS: dict[EventStatus, set[EventStatus]] = {
    EventStatus.draft: {EventStatus.submitted, EventStatus.cancelled},
    EventStatus.submitted: {EventStatus.validated, EventStatus.cancelled},
    EventStatus.validated: {EventStatus.planned, EventStatus.cancelled},
    EventStatus.planned: {EventStatus.confirmed, EventStatus.cancelled},
    EventStatus.confirmed: {EventStatus.in_progress, EventStatus.cancelled},
    EventStatus.in_progress: {EventStatus.completed, EventStatus.cancelled},
    EventStatus.completed: set(),
    EventStatus.cancelled: set(),
}


class EventValidationError(ValueError):
    pass


def _ensure_refs_exist(db: Session, client_id: str, location_id: str) -> None:
    if db.get(Client, client_id) is None:
        raise EventValidationError("client_id does not exist")
    if db.get(Location, location_id) is None:
        raise EventValidationError("location_id does not exist")


def _ensure_status_transition(current: EventStatus, requested: EventStatus) -> None:
    if current == requested:
        return
    allowed = ALLOWED_STATUS_TRANSITIONS.get(current, set())
    if requested not in allowed:
        raise EventValidationError(f"invalid status transition: {current.value} -> {requested.value}")


def create_event(db: Session, payload: EventCreate) -> Event:
    _ensure_refs_exist(db, payload.client_id, payload.location_id)
    event = Event(**payload.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_event(db: Session, event_id: str) -> Event | None:
    return db.get(Event, event_id)


def list_events(db: Session, limit: int, offset: int, status: EventStatus | None) -> tuple[list[Event], int]:
    query = select(Event)
    count_query = select(func.count()).select_from(Event)
    if status is not None:
        query = query.where(Event.status == status)
        count_query = count_query.where(Event.status == status)

    items = (
        db.execute(
            query.order_by(Event.created_at.desc()).offset(offset).limit(limit)
        )
        .scalars()
        .all()
    )
    total = db.scalar(count_query) or 0
    return items, int(total)


def update_event(db: Session, event: Event, payload: EventUpdate) -> Event:
    patch = payload.model_dump(exclude_unset=True)

    client_id = patch.get("client_id", event.client_id)
    location_id = patch.get("location_id", event.location_id)
    _ensure_refs_exist(db, client_id, location_id)

    new_status = patch.get("status")
    if new_status is not None:
        _ensure_status_transition(event.status, new_status)

    planned_start = patch.get("planned_start", event.planned_start)
    planned_end = patch.get("planned_end", event.planned_end)
    if planned_end <= planned_start:
        raise EventValidationError("planned_end must be after planned_start")

    for key, value in patch.items():
        setattr(event, key, value)

    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def delete_event(db: Session, event: Event) -> None:
    db.delete(event)
    db.commit()
