from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.rbac import get_current_auth_payload
from app.models.core import Assignment, EventStatus
from app.schemas.assignments import EventAssignmentListResponse, EventAssignmentRead
from app.schemas.events import EventCreate, EventListResponse, EventRead, EventUpdate
from app.schemas.requirements import EventRequirementCreate, EventRequirementListResponse, EventRequirementRead, EventRequirementUpdate
from app.services.event_service import EventValidationError, create_event, delete_event, get_event, list_events, update_event
from app.services.requirement_service import (
    RequirementValidationError,
    create_requirement,
    delete_requirement,
    get_requirement,
    list_requirements,
    update_requirement,
)


router = APIRouter(prefix="/api/events", tags=["events"])


def _bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("", response_model=EventRead, status_code=status.HTTP_201_CREATED)
def create_event_endpoint(
    payload: EventCreate,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_auth_payload),
) -> EventRead:
    try:
        payload = payload.model_copy(
            update={
                "created_by": payload.created_by or str(auth_payload.get("username", "")),
                "created_by_user_id": payload.created_by_user_id or str(auth_payload.get("sub", "")),
            }
        )
        return create_event(db, payload)
    except EventValidationError as exc:
        raise _bad_request(exc) from exc


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
        raise _bad_request(exc) from exc


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event_endpoint(event_id: str, db: Session = Depends(get_db)) -> Response:
    event = get_event(db, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    delete_event(db, event)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{event_id}/requirements", response_model=EventRequirementRead, status_code=status.HTTP_201_CREATED)
def create_event_requirement_endpoint(
    event_id: str,
    payload: EventRequirementCreate,
    db: Session = Depends(get_db),
) -> EventRequirementRead:
    try:
        return create_requirement(db, event_id, payload)
    except RequirementValidationError as exc:
        raise _bad_request(exc) from exc


@router.get("/{event_id}/requirements", response_model=EventRequirementListResponse)
def list_event_requirements_endpoint(
    event_id: str,
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> EventRequirementListResponse:
    try:
        items, total = list_requirements(db, event_id=event_id, limit=limit, offset=offset)
    except RequirementValidationError as exc:
        raise _bad_request(exc) from exc
    return EventRequirementListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{event_id}/assignments", response_model=EventAssignmentListResponse)
def list_event_assignments_endpoint(
    event_id: str,
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> EventAssignmentListResponse:
    event = get_event(db, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    query = db.query(Assignment).filter(Assignment.event_id == event_id).order_by(Assignment.planned_start.asc())
    total = query.count()
    rows = query.offset(offset).limit(limit).all()
    items = [
        EventAssignmentRead(
            assignment_id=row.assignment_id,
            event_id=row.event_id,
            resource_type=str(row.resource_type.value if hasattr(row.resource_type, "value") else row.resource_type),
            person_id=row.person_id,
            person_name=row.person.full_name if row.person else None,
            equipment_id=row.equipment_id,
            equipment_name=(
                f"{row.equipment.equipment_type.type_name} {row.equipment.asset_tag or row.equipment.serial_number or ''}".strip()
                if row.equipment and row.equipment.equipment_type
                else None
            ),
            vehicle_id=row.vehicle_id,
            vehicle_name=row.vehicle.vehicle_name if row.vehicle else None,
            assignment_role=row.assignment_role,
            planned_start=row.planned_start,
            planned_end=row.planned_end,
            status=str(row.status.value if hasattr(row.status, "value") else row.status),
            is_consumed_in_execution=row.is_consumed_in_execution,
            notes=row.notes,
        )
        for row in rows
    ]
    return EventAssignmentListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{event_id}/requirements/{requirement_id}", response_model=EventRequirementRead)
def get_event_requirement_endpoint(event_id: str, requirement_id: str, db: Session = Depends(get_db)) -> EventRequirementRead:
    item = get_requirement(db, event_id=event_id, requirement_id=requirement_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event requirement not found")
    return item


@router.patch("/{event_id}/requirements/{requirement_id}", response_model=EventRequirementRead)
def update_event_requirement_endpoint(
    event_id: str,
    requirement_id: str,
    payload: EventRequirementUpdate,
    db: Session = Depends(get_db),
) -> EventRequirementRead:
    item = get_requirement(db, event_id=event_id, requirement_id=requirement_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event requirement not found")
    try:
        return update_requirement(db, item, payload)
    except RequirementValidationError as exc:
        raise _bad_request(exc) from exc


@router.delete("/{event_id}/requirements/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event_requirement_endpoint(event_id: str, requirement_id: str, db: Session = Depends(get_db)) -> Response:
    item = get_requirement(db, event_id=event_id, requirement_id=requirement_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event requirement not found")
    delete_requirement(db, item)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
