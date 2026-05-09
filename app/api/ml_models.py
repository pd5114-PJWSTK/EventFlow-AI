from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ai import PredictionType
from app.schemas.ml_models import (
    HardenDurationModelRequest,
    HardenDurationModelResponse,
    ModelRegistryListResponse,
    RetrainDurationModelRequest,
    RetrainDurationModelResponse,
    TrainBaselineModelRequest,
    TrainBaselineModelResponse,
    TrainPlanEvaluatorRequest,
    TrainPlanEvaluatorResponse,
)
from app.services.ml_training_service import (
    ModelTrainingError,
    harden_duration_model,
    list_registered_models,
    retrain_duration_model,
    train_baseline_model,
    train_plan_evaluator_model,
)


router = APIRouter(prefix="/api/ml/models", tags=["ml-models"])


@router.post("/train-baseline", response_model=TrainBaselineModelResponse)
def train_baseline_model_endpoint(
    payload: TrainBaselineModelRequest,
    db: Session = Depends(get_db),
) -> TrainBaselineModelResponse:
    try:
        result = train_baseline_model(db, payload=payload)
        return TrainBaselineModelResponse(
            model=result.model,
            trained_samples=result.trained_samples,
            backend=result.backend,
            artifact_path=result.artifact_path,
        )
    except ModelTrainingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.get("", response_model=ModelRegistryListResponse)
def list_models_endpoint(
    prediction_type: PredictionType | None = Query(default=None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> ModelRegistryListResponse:
    items, total = list_registered_models(
        db, prediction_type=prediction_type, limit=limit
    )
    return ModelRegistryListResponse(items=items, total=total)


@router.post("/harden-duration", response_model=HardenDurationModelResponse)
def harden_duration_model_endpoint(
    payload: HardenDurationModelRequest,
    db: Session = Depends(get_db),
) -> HardenDurationModelResponse:
    try:
        result = harden_duration_model(
            db,
            model_name=payload.model_name,
            activate_model=payload.activate_model,
            required_real_samples=payload.required_real_samples,
            train_samples=payload.train_samples,
            test_samples=payload.test_samples,
            random_seed=payload.random_seed,
        )
        return HardenDurationModelResponse(
            model=result.model,
            trained_samples=result.trained_samples,
            backend=result.backend,
            artifact_path=result.artifact_path,
            real_samples_used=result.real_samples_used,
            train_samples=result.train_samples,
            test_samples=result.test_samples,
            selected_algorithm=result.selected_algorithm,
            validation_summary=result.validation_summary,
        )
    except ModelTrainingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.post("/train-plan-evaluator", response_model=TrainPlanEvaluatorResponse)
def train_plan_evaluator_endpoint(
    payload: TrainPlanEvaluatorRequest,
    db: Session = Depends(get_db),
) -> TrainPlanEvaluatorResponse:
    try:
        result = train_plan_evaluator_model(
            db,
            model_name=payload.model_name,
            activate_model=payload.activate_model,
            required_real_samples=payload.required_real_samples,
            random_seed=payload.random_seed,
        )
        return TrainPlanEvaluatorResponse(
            model=result.model,
            trained_samples=result.trained_samples,
            backend=result.backend,
            artifact_path=result.artifact_path,
            real_samples_used=result.real_samples_used,
            candidate_samples=result.candidate_samples,
            selected_algorithm=result.selected_algorithm,
        )
    except ModelTrainingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.post("/retrain-duration", response_model=RetrainDurationModelResponse)
def retrain_duration_model_endpoint(
    payload: RetrainDurationModelRequest,
    db: Session = Depends(get_db),
) -> RetrainDurationModelResponse:
    try:
        result = retrain_duration_model(
            db,
            model_name=payload.model_name,
            min_samples_required=payload.min_samples_required,
            min_r2_improvement=payload.min_r2_improvement,
            max_mae_ratio=payload.max_mae_ratio,
            force_activate=payload.force_activate,
        )
        return RetrainDurationModelResponse(
            model=result.model,
            trained_samples=result.trained_samples,
            backend=result.backend,
            artifact_path=result.artifact_path,
            activated=result.activated,
            decision_reason=result.decision_reason,
            previous_active_model_id=result.previous_active_model_id,
        )
    except ModelTrainingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
