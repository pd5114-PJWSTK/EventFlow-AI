from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ai import PredictionType
from app.schemas.ml_models import (
    ModelRegistryListResponse,
    RetrainDurationModelRequest,
    RetrainDurationModelResponse,
    TrainBaselineModelRequest,
    TrainBaselineModelResponse,
)
from app.services.ml_training_service import (
    ModelTrainingError,
    list_registered_models,
    retrain_duration_model,
    train_baseline_model,
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
