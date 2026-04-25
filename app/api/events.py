from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.core import EventStatus
from app.schemas.events import EventCreate, EventListResponse, EventRead, EventUpdate
from app.services.event_service import EventValidationError, create_event, delete_event, get_event, list_events, update_event


router = APIRouter(prefix="/api/events", tags=["events"])


@router.post("", response_model=EventRead, status_code=status.HTTP_201_CREATED)
def create_event_endpoint(payload: EventCreate, db: Session = Depends(get_db)) -> EventRead:
    try:
        return create_event(db, payload)
    except EventValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("", response_model=EventListResponse)
def list_events_endpoint(
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status_filter: EventStatus | None = Query(default=None, alias="status"),
) -> EventListResponse:
    items, total = list_events(db, limit=limit, offset=offset, status=status_filter)
    return EventListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{event_id}", response_model=EventRead)
def get_event_endpoint(event_id: str, db: Session = Depends(get_db)) -> EventRead:
    event = get_event(db, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


@router.patch("/{event_id}", response_model=EventRead)
def update_event_endpoint(event_id: str, payload: EventUpdate, db: Session = Depends(get_db)) -> EventRead:
    event = get_event(db, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    try:
        return update_event(db, event, payload)
    except EventValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event_endpoint(event_id: str, db: Session = Depends(get_db)) -> Response:
    event = get_event(db, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    delete_event(db, event)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
