import asyncio

from fastapi import APIRouter, Depends, Query, Response, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.api.error_utils import http_error
from app.database import get_db
from app.middleware.rbac import authorize_websocket, get_current_auth_payload
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
from app.services.idempotency_service import (
    IdempotencyConflictError,
    IdempotencyPendingError,
    complete_idempotency,
    fail_idempotency,
    reserve_idempotency,
)
from app.services.runtime_ops_service import (
    RuntimeOpsError,
    complete_event_execution,
    create_resource_checkpoint,
    report_incident,
    start_event_execution,
)
from app.config import get_settings


router = APIRouter(prefix="/api/runtime", tags=["runtime"])


@router.post("/events/{event_id}/start", response_model=RuntimeStartResponse)
def start_event_endpoint(
    event_id: str,
    payload: RuntimeStartRequest,
    response: Response,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_auth_payload),
) -> RuntimeStartResponse:
    reservation = None
    try:
        reservation = reserve_idempotency(
            db,
            scope="runtime.start",
            idempotency_key=payload.idempotency_key,
            event_id=event_id,
            request_payload=payload.model_dump(mode="json", exclude={"idempotency_key"}),
        )
        if reservation.replayed and reservation.replay_payload is not None:
            response.headers["X-Idempotency-Replayed"] = "true"
            response.headers["X-Operation-Status"] = "success"
            return RuntimeStartResponse.model_validate(reservation.replay_payload)
        result = start_event_execution(
            db,
            event_id=event_id,
            payload=payload,
            actor_user_id=str(auth_payload.get("sub", "")),
            actor_username=str(auth_payload.get("username", "")),
        )
        complete_idempotency(
            db,
            record=reservation.record if reservation else None,
            response_payload=result.model_dump(mode="json"),
        )
        response.headers["X-Operation-Status"] = "success"
        return result
    except IdempotencyConflictError as exc:
        raise http_error(
            status_code=status.HTTP_409_CONFLICT,
            error_code="IDEMPOTENCY_CONFLICT",
            message=str(exc),
        ) from exc
    except IdempotencyPendingError as exc:
        raise http_error(
            status_code=status.HTTP_409_CONFLICT,
            error_code="IDEMPOTENCY_PENDING",
            message=str(exc),
        ) from exc
    except RuntimeOpsError as exc:
        fail_idempotency(
            db,
            record=reservation.record if reservation else None,
            error_code="RUNTIME_OPS_ERROR",
            error_message=str(exc),
        )
        if str(exc) == "Event not found":
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="RUNTIME_EVENT_NOT_FOUND",
                message=str(exc),
            ) from exc
        raise http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="RUNTIME_OPS_ERROR",
            message=str(exc),
        ) from exc


@router.post("/events/{event_id}/checkpoint", response_model=RuntimeCheckpointResponse)
def checkpoint_event_endpoint(
    event_id: str,
    payload: RuntimeCheckpointRequest,
    response: Response,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_auth_payload),
) -> RuntimeCheckpointResponse:
    reservation = None
    try:
        reservation = reserve_idempotency(
            db,
            scope="runtime.checkpoint",
            idempotency_key=payload.idempotency_key,
            event_id=event_id,
            request_payload=payload.model_dump(mode="json", exclude={"idempotency_key"}),
        )
        if reservation.replayed and reservation.replay_payload is not None:
            response.headers["X-Idempotency-Replayed"] = "true"
            response.headers["X-Operation-Status"] = "success"
            return RuntimeCheckpointResponse.model_validate(reservation.replay_payload)
        result = create_resource_checkpoint(
            db,
            event_id=event_id,
            payload=payload,
            actor_user_id=str(auth_payload.get("sub", "")),
            actor_username=str(auth_payload.get("username", "")),
        )
        complete_idempotency(
            db,
            record=reservation.record if reservation else None,
            response_payload=result.model_dump(mode="json"),
        )
        response.headers["X-Operation-Status"] = "success"
        return result
    except IdempotencyConflictError as exc:
        raise http_error(
            status_code=status.HTTP_409_CONFLICT,
            error_code="IDEMPOTENCY_CONFLICT",
            message=str(exc),
        ) from exc
    except IdempotencyPendingError as exc:
        raise http_error(
            status_code=status.HTTP_409_CONFLICT,
            error_code="IDEMPOTENCY_PENDING",
            message=str(exc),
        ) from exc
    except RuntimeOpsError as exc:
        fail_idempotency(
            db,
            record=reservation.record if reservation else None,
            error_code="RUNTIME_OPS_ERROR",
            error_message=str(exc),
        )
        if str(exc) == "Event not found":
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="RUNTIME_EVENT_NOT_FOUND",
                message=str(exc),
            ) from exc
        raise http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="RUNTIME_OPS_ERROR",
            message=str(exc),
        ) from exc


@router.post("/events/{event_id}/incident", response_model=RuntimeIncidentResponse)
def incident_event_endpoint(
    event_id: str,
    payload: RuntimeIncidentRequest,
    response: Response,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_auth_payload),
) -> RuntimeIncidentResponse:
    reservation = None
    try:
        reservation = reserve_idempotency(
            db,
            scope="runtime.incident",
            idempotency_key=payload.idempotency_key,
            event_id=event_id,
            request_payload=payload.model_dump(mode="json", exclude={"idempotency_key"}),
        )
        if reservation.replayed and reservation.replay_payload is not None:
            response.headers["X-Idempotency-Replayed"] = "true"
            response.headers["X-Operation-Status"] = "success"
            return RuntimeIncidentResponse.model_validate(reservation.replay_payload)
        result = report_incident(
            db,
            event_id=event_id,
            payload=payload,
            actor_user_id=str(auth_payload.get("sub", "")),
            actor_username=str(auth_payload.get("username", "")),
        )
        complete_idempotency(
            db,
            record=reservation.record if reservation else None,
            response_payload=result.model_dump(mode="json"),
        )
        response.headers["X-Operation-Status"] = "success"
        return result
    except IdempotencyConflictError as exc:
        raise http_error(
            status_code=status.HTTP_409_CONFLICT,
            error_code="IDEMPOTENCY_CONFLICT",
            message=str(exc),
        ) from exc
    except IdempotencyPendingError as exc:
        raise http_error(
            status_code=status.HTTP_409_CONFLICT,
            error_code="IDEMPOTENCY_PENDING",
            message=str(exc),
        ) from exc
    except RuntimeOpsError as exc:
        fail_idempotency(
            db,
            record=reservation.record if reservation else None,
            error_code="RUNTIME_OPS_ERROR",
            error_message=str(exc),
        )
        if str(exc) == "Event not found":
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="RUNTIME_EVENT_NOT_FOUND",
                message=str(exc),
            ) from exc
        raise http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="RUNTIME_OPS_ERROR",
            message=str(exc),
        ) from exc


@router.post("/events/{event_id}/incident/parse", response_model=RuntimeIncidentParseResponse)
def parse_incident_event_endpoint(
    event_id: str,
    payload: RuntimeIncidentParseRequest,
    response: Response,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_auth_payload),
) -> RuntimeIncidentParseResponse:
    reservation = None
    try:
        reservation = reserve_idempotency(
            db,
            scope="runtime.incident.parse",
            idempotency_key=payload.idempotency_key,
            event_id=event_id,
            request_payload=payload.model_dump(mode="json", exclude={"idempotency_key"}),
        )
        if reservation.replayed and reservation.replay_payload is not None:
            response.headers["X-Idempotency-Replayed"] = "true"
            response.headers["X-Operation-Status"] = "success"
            return RuntimeIncidentParseResponse.model_validate(reservation.replay_payload)
        result = parse_and_report_incident(
            db,
            event_id=event_id,
            payload=payload,
            actor_user_id=str(auth_payload.get("sub", "")),
            actor_username=str(auth_payload.get("username", "")),
        )
        complete_idempotency(
            db,
            record=reservation.record if reservation else None,
            response_payload=result.model_dump(mode="json"),
        )
        response.headers["X-Operation-Status"] = "success"
        return result
    except IdempotencyConflictError as exc:
        raise http_error(
            status_code=status.HTTP_409_CONFLICT,
            error_code="IDEMPOTENCY_CONFLICT",
            message=str(exc),
        ) from exc
    except IdempotencyPendingError as exc:
        raise http_error(
            status_code=status.HTTP_409_CONFLICT,
            error_code="IDEMPOTENCY_PENDING",
            message=str(exc),
        ) from exc
    except RuntimeIncidentParsingError as exc:
        fail_idempotency(
            db,
            record=reservation.record if reservation else None,
            error_code="RUNTIME_INCIDENT_PARSE_ERROR",
            error_message=str(exc),
        )
        raise http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="RUNTIME_INCIDENT_PARSE_ERROR",
            message=str(exc),
        ) from exc
    except RuntimeOpsError as exc:
        fail_idempotency(
            db,
            record=reservation.record if reservation else None,
            error_code="RUNTIME_OPS_ERROR",
            error_message=str(exc),
        )
        if str(exc) == "Event not found":
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="RUNTIME_EVENT_NOT_FOUND",
                message=str(exc),
            ) from exc
        raise http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="RUNTIME_OPS_ERROR",
            message=str(exc),
        ) from exc


@router.post("/events/{event_id}/complete", response_model=RuntimeCompleteResponse)
def complete_event_endpoint(
    event_id: str,
    payload: RuntimeCompleteRequest,
    response: Response,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_auth_payload),
) -> RuntimeCompleteResponse:
    reservation = None
    try:
        reservation = reserve_idempotency(
            db,
            scope="runtime.complete",
            idempotency_key=payload.idempotency_key,
            event_id=event_id,
            request_payload=payload.model_dump(mode="json", exclude={"idempotency_key"}),
        )
        if reservation.replayed and reservation.replay_payload is not None:
            response.headers["X-Idempotency-Replayed"] = "true"
            response.headers["X-Operation-Status"] = "success"
            return RuntimeCompleteResponse.model_validate(reservation.replay_payload)
        result = complete_event_execution(
            db,
            event_id=event_id,
            payload=payload,
            actor_user_id=str(auth_payload.get("sub", "")),
            actor_username=str(auth_payload.get("username", "")),
        )
        complete_idempotency(
            db,
            record=reservation.record if reservation else None,
            response_payload=result.model_dump(mode="json"),
        )
        response.headers["X-Operation-Status"] = "success"
        return result
    except IdempotencyConflictError as exc:
        raise http_error(
            status_code=status.HTTP_409_CONFLICT,
            error_code="IDEMPOTENCY_CONFLICT",
            message=str(exc),
        ) from exc
    except IdempotencyPendingError as exc:
        raise http_error(
            status_code=status.HTTP_409_CONFLICT,
            error_code="IDEMPOTENCY_PENDING",
            message=str(exc),
        ) from exc
    except RuntimeOpsError as exc:
        fail_idempotency(
            db,
            record=reservation.record if reservation else None,
            error_code="RUNTIME_OPS_ERROR",
            error_message=str(exc),
        )
        if str(exc) == "Event not found":
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="RUNTIME_EVENT_NOT_FOUND",
                message=str(exc),
            ) from exc
        raise http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="RUNTIME_OPS_ERROR",
            message=str(exc),
        ) from exc


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
async def runtime_notifications_websocket(
    websocket: WebSocket,
    event_id: str,
    db: Session = Depends(get_db),
) -> None:
    settings = get_settings()
    payload = await authorize_websocket(
        websocket,
        allowed_roles=["manager", "coordinator", "technician"],
        settings=settings,
        db=db,
    )
    if payload is None:
        return
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
