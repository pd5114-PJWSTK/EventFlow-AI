from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ai import PredictionType
from app.schemas.ml_predictions import (
    EvaluatePredictionRequest,
    EvaluatePredictionResponse,
    GeneratePredictionRequest,
    GeneratePredictionResponse,
    PredictionListResponse,
)
from app.services.ml_inference_service import (
    PredictionServiceError,
    evaluate_prediction,
    generate_prediction,
    list_predictions,
)


router = APIRouter(prefix="/api/ml/predictions", tags=["ml-predictions"])


@router.post("", response_model=GeneratePredictionResponse)
def generate_prediction_endpoint(
    payload: GeneratePredictionRequest,
    db: Session = Depends(get_db),
) -> GeneratePredictionResponse:
    try:
        return generate_prediction(db, payload=payload)
    except PredictionServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.post("/{prediction_id}/evaluate", response_model=EvaluatePredictionResponse)
def evaluate_prediction_endpoint(
    prediction_id: str,
    payload: EvaluatePredictionRequest,
    db: Session = Depends(get_db),
) -> EvaluatePredictionResponse:
    try:
        return evaluate_prediction(db, prediction_id=prediction_id, payload=payload)
    except PredictionServiceError as exc:
        if str(exc) == "Prediction not found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.get("", response_model=PredictionListResponse)
def list_predictions_endpoint(
    event_id: str | None = Query(default=None),
    prediction_type: PredictionType | None = Query(default=None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> PredictionListResponse:
    return list_predictions(
        db,
        event_id=event_id,
        prediction_type=prediction_type,
        limit=limit,
    )
