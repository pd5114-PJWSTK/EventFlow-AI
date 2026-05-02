from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.error_utils import http_error
from app.database import get_db
from app.schemas.planner import (
    ConstraintCheckRequest,
    ConstraintCheckResponse,
    GeneratePlanRequest,
    GeneratePlanResponse,
    RecommendBestPlanRequest,
    RecommendBestPlanResponse,
    ResolvePlanGapsRequest,
    ResolvePlanGapsResponse,
    ReplanRequest,
    ReplanResponse,
)
from app.services.planner_generation_service import (
    PlanGenerationError,
    generate_plan,
    recommend_best_plan_with_ml,
    resolve_plan_gaps,
    replan_event,
)
from app.services.idempotency_service import (
    IdempotencyConflictError,
    IdempotencyPendingError,
    complete_idempotency,
    fail_idempotency,
    reserve_idempotency,
)
from app.services.planner_input_builder import PlannerInputError
from app.services.validation_service import ValidationError, validate_event_constraints


router = APIRouter(prefix="/api/planner", tags=["planner"])


@router.post("/validate-constraints", response_model=ConstraintCheckResponse)
def validate_constraints_endpoint(
    payload: ConstraintCheckRequest,
    db: Session = Depends(get_db),
) -> ConstraintCheckResponse:
    try:
        return validate_event_constraints(db, payload.event_id)
    except ValidationError as exc:
        if str(exc) == "Event not found":
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="PLANNER_EVENT_NOT_FOUND",
                message=str(exc),
            ) from exc
        raise http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="PLANNER_VALIDATION_ERROR",
            message=str(exc),
        ) from exc


@router.post("/generate-plan", response_model=GeneratePlanResponse)
def generate_plan_endpoint(
    payload: GeneratePlanRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> GeneratePlanResponse:
    try:
        result = generate_plan(
            db,
            event_id=payload.event_id,
            initiated_by=payload.initiated_by,
            trigger_reason=payload.trigger_reason,
            commit_to_assignments=payload.commit_to_assignments,
            solver_timeout_seconds=payload.solver_timeout_seconds,
            fallback_enabled=payload.fallback_enabled,
        )
        response.headers["X-Operation-Status"] = "success"
        return result
    except PlannerInputError as exc:
        if str(exc) == "Event not found":
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="PLANNER_EVENT_NOT_FOUND",
                message=str(exc),
            ) from exc
        raise http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="PLANNER_INPUT_ERROR",
            message=str(exc),
        ) from exc
    except PlanGenerationError as exc:
        raise http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="PLANNER_GENERATION_ERROR",
            message=str(exc),
        ) from exc


@router.post("/replan/{event_id}", response_model=ReplanResponse)
def replan_event_endpoint(
    event_id: str,
    payload: ReplanRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> ReplanResponse:
    reservation = None
    try:
        reservation = reserve_idempotency(
            db,
            scope="planner.replan",
            idempotency_key=payload.idempotency_key,
            event_id=event_id,
            request_payload=payload.model_dump(mode="json", exclude={"idempotency_key"}),
        )
        if reservation.replayed and reservation.replay_payload is not None:
            response.headers["X-Idempotency-Replayed"] = "true"
            response.headers["X-Operation-Status"] = "success"
            return ReplanResponse.model_validate(reservation.replay_payload)
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

    try:
        result = replan_event(
            db,
            event_id=event_id,
            incident_id=payload.incident_id,
            incident_summary=payload.incident_summary,
            initiated_by=payload.initiated_by,
            commit_to_assignments=payload.commit_to_assignments,
            solver_timeout_seconds=payload.solver_timeout_seconds,
            fallback_enabled=payload.fallback_enabled,
            preserve_consumed_resources=payload.preserve_consumed_resources,
            expected_event_updated_at=payload.expected_event_updated_at,
        )
        complete_idempotency(
            db,
            record=reservation.record if reservation else None,
            response_payload=result.model_dump(mode="json"),
        )
        response.headers["X-Operation-Status"] = "success"
        return result
    except PlannerInputError as exc:
        fail_idempotency(
            db,
            record=reservation.record if reservation else None,
            error_code="PLANNER_INPUT_ERROR",
            error_message=str(exc),
        )
        if str(exc) == "Event not found":
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="PLANNER_EVENT_NOT_FOUND",
                message=str(exc),
            ) from exc
        raise http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="PLANNER_INPUT_ERROR",
            message=str(exc),
        ) from exc
    except PlanGenerationError as exc:
        fail_idempotency(
            db,
            record=reservation.record if reservation else None,
            error_code="PLANNER_GENERATION_ERROR",
            error_message=str(exc),
        )
        raise http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="PLANNER_GENERATION_ERROR",
            message=str(exc),
        ) from exc


@router.post("/recommend-best-plan", response_model=RecommendBestPlanResponse)
def recommend_best_plan_endpoint(
    payload: RecommendBestPlanRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> RecommendBestPlanResponse:
    try:
        result = recommend_best_plan_with_ml(
            db,
            event_id=payload.event_id,
            initiated_by=payload.initiated_by,
            commit_to_assignments=payload.commit_to_assignments,
            solver_timeout_seconds=payload.solver_timeout_seconds,
            fallback_enabled=payload.fallback_enabled,
            duration_model_id=payload.duration_model_id,
            plan_evaluator_model_id=payload.plan_evaluator_model_id,
        )
        response.headers["X-Operation-Status"] = "success"
        return result
    except PlannerInputError as exc:
        if str(exc) == "Event not found":
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="PLANNER_EVENT_NOT_FOUND",
                message=str(exc),
            ) from exc
        raise http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="PLANNER_INPUT_ERROR",
            message=str(exc),
        ) from exc
    except PlanGenerationError as exc:
        raise http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="PLANNER_GENERATION_ERROR",
            message=str(exc),
        ) from exc


@router.post("/resolve-gaps/{event_id}", response_model=ResolvePlanGapsResponse)
def resolve_plan_gaps_endpoint(
    event_id: str,
    payload: ResolvePlanGapsRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> ResolvePlanGapsResponse:
    reservation = None
    try:
        reservation = reserve_idempotency(
            db,
            scope="planner.resolve_gaps",
            idempotency_key=payload.idempotency_key,
            event_id=event_id,
            request_payload=payload.model_dump(mode="json", exclude={"idempotency_key"}),
        )
        if reservation.replayed and reservation.replay_payload is not None:
            response.headers["X-Idempotency-Replayed"] = "true"
            response.headers["X-Operation-Status"] = "success"
            return ResolvePlanGapsResponse.model_validate(reservation.replay_payload)
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

    try:
        result = resolve_plan_gaps(
            db,
            event_id=event_id,
            payload=payload,
        )
        complete_idempotency(
            db,
            record=reservation.record if reservation else None,
            response_payload=result.model_dump(mode="json"),
        )
        response.headers["X-Operation-Status"] = "success"
        return result
    except PlannerInputError as exc:
        fail_idempotency(
            db,
            record=reservation.record if reservation else None,
            error_code="PLANNER_INPUT_ERROR",
            error_message=str(exc),
        )
        if str(exc) == "Event not found":
            raise http_error(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="PLANNER_EVENT_NOT_FOUND",
                message=str(exc),
            ) from exc
        raise http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="PLANNER_INPUT_ERROR",
            message=str(exc),
        ) from exc
    except PlanGenerationError as exc:
        fail_idempotency(
            db,
            record=reservation.record if reservation else None,
            error_code="PLANNER_GENERATION_ERROR",
            error_message=str(exc),
        )
        raise http_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="PLANNER_GENERATION_ERROR",
            message=str(exc),
        ) from exc
