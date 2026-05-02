import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.runtime_ops import (
    RuntimeCheckpointRequest,
    RuntimeCheckpointResponse,
    RuntimeCompleteRequest,
    RuntimeCompleteResponse,
    RuntimeIncidentParseRequest,
    RuntimeIncidentParseResponse,
    RuntimeIncidentRequest,
    RuntimeIncidentResponse,
    RuntimeNotificationFeedResponse,
    RuntimeStartRequest,
    RuntimeStartResponse,
)
from app.services.runtime_notification_service import list_runtime_notifications
from app.services.runtime_incident_parser import (
    RuntimeIncidentParsingError,
    parse_and_report_incident,
)
from app.services.runtime_ops_service import (
    RuntimeOpsError,
    complete_event_execution,
    create_resource_checkpoint,
    report_incident,
    start_event_execution,
)


router = APIRouter(prefix="/api/runtime", tags=["runtime"])


@router.post("/events/{event_id}/start", response_model=RuntimeStartResponse)
def start_event_endpoint(
    event_id: str,
    payload: RuntimeStartRequest,
    db: Session = Depends(get_db),
) -> RuntimeStartResponse:
    try:
        return start_event_execution(db, event_id=event_id, payload=payload)
    except RuntimeOpsError as exc:
        if str(exc) == "Event not found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/events/{event_id}/checkpoint", response_model=RuntimeCheckpointResponse)
def checkpoint_event_endpoint(
    event_id: str,
    payload: RuntimeCheckpointRequest,
    db: Session = Depends(get_db),
) -> RuntimeCheckpointResponse:
    try:
        return create_resource_checkpoint(db, event_id=event_id, payload=payload)
    except RuntimeOpsError as exc:
        if str(exc) == "Event not found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/events/{event_id}/incident", response_model=RuntimeIncidentResponse)
def incident_event_endpoint(
    event_id: str,
    payload: RuntimeIncidentRequest,
    db: Session = Depends(get_db),
) -> RuntimeIncidentResponse:
    try:
        return report_incident(db, event_id=event_id, payload=payload)
    except RuntimeOpsError as exc:
        if str(exc) == "Event not found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/events/{event_id}/incident/parse", response_model=RuntimeIncidentParseResponse)
def parse_incident_event_endpoint(
    event_id: str,
    payload: RuntimeIncidentParseRequest,
    db: Session = Depends(get_db),
) -> RuntimeIncidentParseResponse:
    try:
        return parse_and_report_incident(db, event_id=event_id, payload=payload)
    except RuntimeIncidentParsingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except RuntimeOpsError as exc:
        if str(exc) == "Event not found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/events/{event_id}/complete", response_model=RuntimeCompleteResponse)
def complete_event_endpoint(
    event_id: str,
    payload: RuntimeCompleteRequest,
    db: Session = Depends(get_db),
) -> RuntimeCompleteResponse:
    try:
        return complete_event_execution(db, event_id=event_id, payload=payload)
    except RuntimeOpsError as exc:
        if str(exc) == "Event not found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/events/{event_id}/notifications", response_model=RuntimeNotificationFeedResponse)
def runtime_notifications_endpoint(
    event_id: str,
    limit: int = Query(50, ge=1, le=200),
) -> RuntimeNotificationFeedResponse:
    items = list_runtime_notifications(event_id, limit=limit)
    return RuntimeNotificationFeedResponse(
        event_id=event_id,
        items=items,
        total=len(items),
    )


@router.websocket("/ws/events/{event_id}/notifications")
async def runtime_notifications_websocket(websocket: WebSocket, event_id: str) -> None:
    await websocket.accept()
    last_fingerprint = ""
    try:
        while True:
            items = list_runtime_notifications(event_id, limit=50)
            fingerprint = items[-1]["emitted_at"] if items else ""
            if fingerprint != last_fingerprint:
                await websocket.send_json(
                    {
                        "event_id": event_id,
                        "items": items,
                        "total": len(items),
                    }
                )
                last_fingerprint = fingerprint
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return
