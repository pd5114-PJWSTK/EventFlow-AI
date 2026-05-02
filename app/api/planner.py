from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.planner import (
    ConstraintCheckRequest,
    ConstraintCheckResponse,
    GeneratePlanRequest,
    GeneratePlanResponse,
    RecommendBestPlanRequest,
    RecommendBestPlanResponse,
    ReplanRequest,
    ReplanResponse,
)
from app.services.planner_generation_service import (
    PlanGenerationError,
    generate_plan,
    recommend_best_plan_with_ml,
    replan_event,
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.post("/generate-plan", response_model=GeneratePlanResponse)
def generate_plan_endpoint(
    payload: GeneratePlanRequest,
    db: Session = Depends(get_db),
) -> GeneratePlanResponse:
    try:
        return generate_plan(
            db,
            event_id=payload.event_id,
            initiated_by=payload.initiated_by,
            trigger_reason=payload.trigger_reason,
            commit_to_assignments=payload.commit_to_assignments,
            solver_timeout_seconds=payload.solver_timeout_seconds,
            fallback_enabled=payload.fallback_enabled,
        )
    except PlannerInputError as exc:
        if str(exc) == "Event not found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except PlanGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.post("/replan/{event_id}", response_model=ReplanResponse)
def replan_event_endpoint(
    event_id: str,
    payload: ReplanRequest,
    db: Session = Depends(get_db),
) -> ReplanResponse:
    try:
        return replan_event(
            db,
            event_id=event_id,
            incident_id=payload.incident_id,
            incident_summary=payload.incident_summary,
            initiated_by=payload.initiated_by,
            commit_to_assignments=payload.commit_to_assignments,
            solver_timeout_seconds=payload.solver_timeout_seconds,
            fallback_enabled=payload.fallback_enabled,
        )
    except PlannerInputError as exc:
        if str(exc) == "Event not found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except PlanGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.post("/recommend-best-plan", response_model=RecommendBestPlanResponse)
def recommend_best_plan_endpoint(
    payload: RecommendBestPlanRequest,
    db: Session = Depends(get_db),
) -> RecommendBestPlanResponse:
    try:
        return recommend_best_plan_with_ml(
            db,
            event_id=payload.event_id,
            initiated_by=payload.initiated_by,
            commit_to_assignments=payload.commit_to_assignments,
            solver_timeout_seconds=payload.solver_timeout_seconds,
            fallback_enabled=payload.fallback_enabled,
            duration_model_id=payload.duration_model_id,
            plan_evaluator_model_id=payload.plan_evaluator_model_id,
        )
    except PlannerInputError as exc:
        if str(exc) == "Event not found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except PlanGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
