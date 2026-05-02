from __future__ import annotations

import pickle
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from app.models.ai import (
    EventFeature,
    ModelRegistry,
    ModelStatus,
    Prediction,
    PredictionOutcome,
    PredictionType,
)
from app.models.ops import ActualTiming
from app.schemas.ml_predictions import (
    EvaluatePredictionRequest,
    EvaluatePredictionResponse,
    GeneratePredictionRequest,
    GeneratePredictionResponse,
    PredictionListResponse,
    PredictionOutcomeRead,
    PredictionRead,
)


class PredictionServiceError(ValueError):
    pass


@dataclass
class _ModelExecutionContext:
    model: ModelRegistry
    artifact: dict[str, Any]


def generate_prediction(
    db: Session,
    *,
    payload: GeneratePredictionRequest,
) -> GeneratePredictionResponse:
    if payload.prediction_type != PredictionType.duration_estimate:
        raise PredictionServiceError(
            "Only duration_estimate inference is supported in phase-7-cp-03."
        )

    event_feature = db.get(EventFeature, payload.event_id)
    if event_feature is None:
        raise PredictionServiceError("Event feature snapshot not found for event.")

    context = _resolve_model_context(
        db=db,
        prediction_type=payload.prediction_type,
        model_id=payload.model_id,
    )
    feature_vector = _feature_vector(event_feature)
    predicted_value = _run_prediction(context.artifact, feature_vector)
    confidence = _estimate_confidence(
        predicted_value=predicted_value,
        mae_minutes=(context.model.metrics or {}).get("mae_minutes"),
    )

    feature_snapshot = _event_feature_snapshot(event_feature)
    prediction = Prediction(
        event_id=payload.event_id,
        assignment_id=payload.assignment_id,
        model_id=context.model.model_id,
        prediction_type=payload.prediction_type,
        predicted_value=_quantize(predicted_value, "0.0001"),
        confidence_score=_quantize(confidence, "0.0001"),
        explanation=payload.explanation
        or f"Predicted using {context.model.model_name}:{context.model.model_version}",
        feature_snapshot=feature_snapshot,
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)

    return GeneratePredictionResponse(
        prediction=_to_prediction_read(prediction),
        model_name=context.model.model_name,
        model_version=context.model.model_version,
    )


def evaluate_prediction(
    db: Session,
    *,
    prediction_id: str,
    payload: EvaluatePredictionRequest,
) -> EvaluatePredictionResponse:
    prediction = db.get(Prediction, prediction_id)
    if prediction is None:
        raise PredictionServiceError("Prediction not found")

    actual_numeric = payload.actual_numeric_value
    actual_label = payload.actual_label
    notes = payload.notes

    if payload.auto_resolve_actual:
        resolved = _resolve_actual_from_runtime(db, prediction)
        if resolved is None:
            raise PredictionServiceError(
                "Unable to auto-resolve actual value from runtime data."
            )
        actual_numeric = resolved
        notes = notes or "Auto-resolved from ops.actual_timings."

    error_value = _compute_error_value(
        predicted_value=prediction.predicted_value,
        actual_numeric_value=actual_numeric,
    )

    outcome = PredictionOutcome(
        prediction_id=prediction.prediction_id,
        actual_numeric_value=actual_numeric,
        actual_label=actual_label,
        error_value=error_value,
        notes=notes,
    )
    db.add(outcome)
    db.commit()
    db.refresh(prediction)
    db.refresh(outcome)

    return EvaluatePredictionResponse(
        prediction=_to_prediction_read(prediction),
        outcome=_to_prediction_outcome_read(outcome),
    )


def list_predictions(
    db: Session,
    *,
    event_id: str | None = None,
    prediction_type: PredictionType | None = None,
    limit: int = 100,
) -> PredictionListResponse:
    query = db.query(Prediction).order_by(Prediction.generated_at.desc())
    if event_id is not None:
        query = query.filter(Prediction.event_id == event_id)
    if prediction_type is not None:
        query = query.filter(Prediction.prediction_type == prediction_type)
    items = query.limit(limit).all()
    return PredictionListResponse(
        items=[_to_prediction_read(item) for item in items],
        total=len(items),
    )


def _resolve_model_context(
    *,
    db: Session,
    prediction_type: PredictionType,
    model_id: str | None,
) -> _ModelExecutionContext:
    model = None
    if model_id is not None:
        model = db.get(ModelRegistry, model_id)
        if model is None:
            raise PredictionServiceError("Model not found")
    else:
        model = (
            db.query(ModelRegistry)
            .filter(
                ModelRegistry.prediction_type == prediction_type,
                ModelRegistry.status == ModelStatus.active,
            )
            .order_by(ModelRegistry.created_at.desc())
            .first()
        )
        if model is None:
            raise PredictionServiceError("Active model not found for prediction type")

    if model.prediction_type != prediction_type:
        raise PredictionServiceError("Model prediction_type does not match request.")

    metrics = model.metrics or {}
    artifact_path = metrics.get("artifact_path")
    if not artifact_path:
        raise PredictionServiceError("Model artifact path missing in metrics.")
    artifact = _load_artifact(artifact_path)
    return _ModelExecutionContext(model=model, artifact=artifact)


def _load_artifact(path: str) -> dict[str, Any]:
    model_path = Path(path)
    if not model_path.exists():
        raise PredictionServiceError(f"Model artifact not found: {path}")
    with model_path.open("rb") as file_obj:
        loaded = pickle.load(file_obj)
    if not isinstance(loaded, dict) or "kind" not in loaded:
        raise PredictionServiceError("Model artifact has invalid format.")
    return loaded


def _feature_vector(feature: EventFeature) -> list[float]:
    return [
        float(feature.feature_attendee_count or 0),
        float(feature.feature_setup_complexity_score or 0),
        float(feature.feature_access_difficulty or 0),
        float(feature.feature_parking_difficulty or 0),
        float(feature.feature_required_person_count or 0),
        float(feature.feature_required_equipment_count or 0),
        float(feature.feature_required_vehicle_count or 0),
        float(_priority_to_score(feature.feature_priority)),
        float(feature.feature_day_of_week or 0),
        float(feature.feature_month or 0),
        float(_season_to_score(feature.feature_season)),
        1.0 if feature.feature_requires_transport else 0.0,
        1.0 if feature.feature_requires_setup else 0.0,
        1.0 if feature.feature_requires_teardown else 0.0,
    ]


def _run_prediction(artifact: dict[str, Any], feature_vector: list[float]) -> Decimal:
    kind = str(artifact.get("kind", ""))
    if kind == "mean_regressor":
        value = artifact.get("mean_value", 0.0)
        return _quantize(Decimal(str(value)), "0.0001")
    if kind in {"sklearn_linear_regression", "sklearn_estimator"}:
        model = artifact.get("model")
        if model is None:
            raise PredictionServiceError("Missing sklearn model in artifact.")
        predicted = float(model.predict([feature_vector])[0])
        return _quantize(Decimal(str(max(predicted, 0.0))), "0.0001")
    raise PredictionServiceError(f"Unsupported model artifact kind: {kind}")


def _estimate_confidence(
    *,
    predicted_value: Decimal,
    mae_minutes: float | int | str | None,
) -> Decimal:
    if mae_minutes is None:
        return Decimal("0.7000")
    try:
        mae = Decimal(str(mae_minutes))
    except Exception:
        return Decimal("0.7000")
    denominator = max(predicted_value, Decimal("1"))
    confidence = Decimal("1") - min(mae / denominator, Decimal("1"))
    confidence = max(Decimal("0.05"), min(confidence, Decimal("0.99")))
    return _quantize(confidence, "0.0001")


def _resolve_actual_from_runtime(
    db: Session, prediction: Prediction
) -> Decimal | None:
    if prediction.prediction_type != PredictionType.duration_estimate:
        return None
    if prediction.event_id is None:
        return None

    timings = (
        db.query(ActualTiming)
        .filter(
            ActualTiming.event_id == prediction.event_id,
            ActualTiming.actual_start.is_not(None),
            ActualTiming.actual_end.is_not(None),
        )
        .all()
    )
    if not timings:
        return None

    starts = [timing.actual_start for timing in timings if timing.actual_start is not None]
    ends = [timing.actual_end for timing in timings if timing.actual_end is not None]
    if not starts or not ends:
        return None

    actual_minutes = (max(ends) - min(starts)).total_seconds() / 60
    if actual_minutes < 0:
        return None
    return _quantize(Decimal(str(actual_minutes)), "0.0001")


def _compute_error_value(
    *,
    predicted_value: Decimal | None,
    actual_numeric_value: Decimal | None,
) -> Decimal | None:
    if predicted_value is None or actual_numeric_value is None:
        return None
    return _quantize(abs(actual_numeric_value - predicted_value), "0.0001")


def _event_feature_snapshot(feature: EventFeature) -> dict[str, Any]:
    return {
        "event_id": feature.event_id,
        "attendee_count": feature.feature_attendee_count,
        "setup_complexity_score": feature.feature_setup_complexity_score,
        "access_difficulty": feature.feature_access_difficulty,
        "parking_difficulty": feature.feature_parking_difficulty,
        "required_person_count": feature.feature_required_person_count,
        "required_equipment_count": feature.feature_required_equipment_count,
        "required_vehicle_count": feature.feature_required_vehicle_count,
        "priority": feature.feature_priority,
        "day_of_week": feature.feature_day_of_week,
        "month": feature.feature_month,
        "season": feature.feature_season,
        "requires_transport": feature.feature_requires_transport,
        "requires_setup": feature.feature_requires_setup,
        "requires_teardown": feature.feature_requires_teardown,
        "generated_at": feature.generated_at.isoformat(),
    }


def _to_prediction_read(item: Prediction) -> PredictionRead:
    return PredictionRead(
        prediction_id=item.prediction_id,
        event_id=item.event_id,
        assignment_id=item.assignment_id,
        model_id=item.model_id,
        prediction_type=item.prediction_type,
        predicted_value=item.predicted_value,
        predicted_label=item.predicted_label,
        confidence_score=item.confidence_score,
        explanation=item.explanation,
        feature_snapshot=item.feature_snapshot or {},
        generated_at=item.generated_at,
    )


def _to_prediction_outcome_read(item: PredictionOutcome) -> PredictionOutcomeRead:
    return PredictionOutcomeRead(
        prediction_outcome_id=item.prediction_outcome_id,
        prediction_id=item.prediction_id,
        actual_numeric_value=item.actual_numeric_value,
        actual_label=item.actual_label,
        evaluated_at=item.evaluated_at,
        error_value=item.error_value,
        notes=item.notes,
    )


def _priority_to_score(priority: str | None) -> int:
    mapping = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    return mapping.get((priority or "medium").lower(), 2)


def _season_to_score(season: str | None) -> int:
    mapping = {"winter": 1, "spring": 2, "summer": 3, "autumn": 4}
    return mapping.get((season or "").lower(), 0)


def _quantize(value: Decimal, places: str) -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)
