from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from statistics import mean

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.ai import ModelRegistry, ModelStatus, PredictionType
from app.models.core import Event
from app.models.ops import ActualTiming
from app.schemas.ml_models import ModelRegistryRead, TrainBaselineModelRequest


class ModelTrainingError(ValueError):
    pass


@dataclass
class TrainBaselineModelResult:
    model: ModelRegistryRead
    trained_samples: int
    backend: str
    artifact_path: str | None = None


@dataclass
class _TrainingSample:
    event_id: str
    x: list[float]
    y: float
    observed_at: datetime


def train_baseline_model(
    db: Session,
    *,
    payload: TrainBaselineModelRequest,
) -> TrainBaselineModelResult:
    if payload.prediction_type != PredictionType.duration_estimate:
        raise ModelTrainingError(
            "Only duration_estimate baseline training is supported in phase-7-cp-02."
        )

    samples, feature_names = _collect_duration_training_samples(db)
    if len(samples) < 1:
        raise ModelTrainingError(
            "No training samples found. Generate event features and runtime timings first."
        )

    settings = get_settings()
    backend = "heuristic_mean_regressor"
    artifact_payload: dict = {}
    predictions: list[float]
    y_values = [sample.y for sample in samples]

    sklearn_result = _try_train_sklearn(samples)
    if sklearn_result is not None and len(samples) >= settings.ml_min_training_samples:
        backend = "sklearn_linear_regression"
        artifact_payload = sklearn_result["artifact"]
        predictions = sklearn_result["predictions"]
    else:
        mean_value = mean(y_values)
        predictions = [mean_value for _ in y_values]
        artifact_payload = {
            "kind": "mean_regressor",
            "mean_value": mean_value,
            "feature_names": feature_names,
        }

    metrics = _build_metrics(
        y_true=y_values,
        y_pred=predictions,
        sample_count=len(samples),
        backend=backend,
        feature_names=feature_names,
    )
    version = datetime.now(UTC).strftime("v%Y%m%d%H%M%S")

    if payload.activate_model:
        (
            db.query(ModelRegistry)
            .filter(
                ModelRegistry.model_name == payload.model_name,
                ModelRegistry.prediction_type == payload.prediction_type,
                ModelRegistry.status == ModelStatus.active,
            )
            .update({ModelRegistry.status: ModelStatus.deprecated}, synchronize_session=False)
        )

    model = ModelRegistry(
        model_name=payload.model_name,
        model_version=version,
        prediction_type=payload.prediction_type,
        status=ModelStatus.active if payload.activate_model else ModelStatus.training,
        training_data_from=min(sample.observed_at for sample in samples),
        training_data_to=max(sample.observed_at for sample in samples),
        metrics=metrics,
    )
    db.add(model)
    db.flush()

    artifact_path = _save_model_artifact(
        model_name=payload.model_name,
        model_version=version,
        model_id=model.model_id,
        prediction_type=payload.prediction_type.value,
        backend=backend,
        feature_names=feature_names,
        metrics=metrics,
        artifact_payload=artifact_payload,
    )

    model.metrics = {**model.metrics, "artifact_path": artifact_path}
    db.commit()
    db.refresh(model)

    return TrainBaselineModelResult(
        model=_to_model_read(model),
        trained_samples=len(samples),
        backend=backend,
        artifact_path=artifact_path,
    )


def list_registered_models(
    db: Session,
    *,
    prediction_type: PredictionType | None = None,
    limit: int = 100,
) -> tuple[list[ModelRegistryRead], int]:
    query = db.query(ModelRegistry).order_by(ModelRegistry.created_at.desc())
    if prediction_type is not None:
        query = query.filter(ModelRegistry.prediction_type == prediction_type)
    items = query.limit(limit).all()
    return ([_to_model_read(item) for item in items], len(items))


def _collect_duration_training_samples(
    db: Session,
) -> tuple[list[_TrainingSample], list[str]]:
    from app.models.ai import EventFeature

    features = db.query(EventFeature).all()
    if not features:
        return [], []

    timings = (
        db.query(ActualTiming)
        .filter(
            ActualTiming.actual_start.is_not(None),
            ActualTiming.actual_end.is_not(None),
        )
        .all()
    )

    window_by_event: dict[str, tuple[datetime, datetime]] = {}
    for timing in timings:
        if timing.event_id is None:
            continue
        current = window_by_event.get(timing.event_id)
        start = timing.actual_start
        end = timing.actual_end
        if current is None:
            window_by_event[timing.event_id] = (start, end)
            continue
        window_by_event[timing.event_id] = (
            min(current[0], start),
            max(current[1], end),
        )

    feature_names = [
        "attendee_count",
        "setup_complexity",
        "access_difficulty",
        "parking_difficulty",
        "required_person_count",
        "required_equipment_count",
        "required_vehicle_count",
        "priority_score",
        "day_of_week",
        "month",
        "season_score",
        "requires_transport",
        "requires_setup",
        "requires_teardown",
    ]

    event_lookup = {
        event.event_id: event for event in db.query(Event.event_id, Event.created_at).all()
    }
    samples: list[_TrainingSample] = []

    for feature in features:
        time_window = window_by_event.get(feature.event_id)
        if time_window is None:
            continue

        actual_minutes = (time_window[1] - time_window[0]).total_seconds() / 60
        if actual_minutes <= 0:
            continue

        observed_at = event_lookup.get(feature.event_id, None)
        observed_time = (
            observed_at.created_at
            if observed_at is not None and observed_at.created_at is not None
            else feature.generated_at
        )

        x_vector = [
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
        samples.append(
            _TrainingSample(
                event_id=feature.event_id,
                x=x_vector,
                y=float(actual_minutes),
                observed_at=observed_time,
            )
        )

    return samples, feature_names


def _try_train_sklearn(samples: list[_TrainingSample]) -> dict | None:
    try:
        from sklearn.linear_model import LinearRegression
    except Exception:
        return None

    x_values = [sample.x for sample in samples]
    y_values = [sample.y for sample in samples]
    model = LinearRegression()
    model.fit(x_values, y_values)
    y_pred = list(model.predict(x_values))
    return {
        "predictions": y_pred,
        "artifact": {
            "kind": "sklearn_linear_regression",
            "model": model,
        },
    }


def _build_metrics(
    *,
    y_true: list[float],
    y_pred: list[float],
    sample_count: int,
    backend: str,
    feature_names: list[str],
) -> dict:
    if len(y_true) != len(y_pred):
        raise ModelTrainingError("Prediction and target vectors have different lengths.")

    abs_errors = [abs(target - predicted) for target, predicted in zip(y_true, y_pred)]
    squared_errors = [
        (target - predicted) ** 2 for target, predicted in zip(y_true, y_pred)
    ]
    mae = float(mean(abs_errors)) if abs_errors else 0.0
    mse = float(mean(squared_errors)) if squared_errors else 0.0
    rmse = mse**0.5

    y_mean = float(mean(y_true)) if y_true else 0.0
    total_variance = sum((value - y_mean) ** 2 for value in y_true)
    residual_variance = sum((target - predicted) ** 2 for target, predicted in zip(y_true, y_pred))
    r2 = 0.0
    if total_variance > 0:
        r2 = 1.0 - (residual_variance / total_variance)

    return {
        "sample_count": sample_count,
        "backend": backend,
        "mae_minutes": round(mae, 4),
        "rmse_minutes": round(rmse, 4),
        "r2": round(r2, 6),
        "feature_names": feature_names,
        "trained_at": datetime.now(UTC).isoformat(),
    }


def _save_model_artifact(
    *,
    model_name: str,
    model_version: str,
    model_id: str,
    prediction_type: str,
    backend: str,
    feature_names: list[str],
    metrics: dict,
    artifact_payload: dict,
) -> str:
    settings = get_settings()
    artifact_dir = Path(settings.ml_models_dir).resolve()
    model_dir = artifact_dir / model_name / model_version
    model_dir.mkdir(parents=True, exist_ok=True)

    metadata_path = model_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "model_id": model_id,
                "model_name": model_name,
                "model_version": model_version,
                "prediction_type": prediction_type,
                "backend": backend,
                "feature_names": feature_names,
                "metrics": metrics,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    model_path = model_dir / "model.pkl"
    with model_path.open("wb") as file_obj:
        pickle.dump(artifact_payload, file_obj)

    return str(model_path)


def _priority_to_score(priority: str | None) -> int:
    mapping = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    return mapping.get((priority or "medium").lower(), 2)


def _season_to_score(season: str | None) -> int:
    mapping = {"winter": 1, "spring": 2, "summer": 3, "autumn": 4}
    return mapping.get((season or "").lower(), 0)


def _to_model_read(model: ModelRegistry) -> ModelRegistryRead:
    return ModelRegistryRead(
        model_id=model.model_id,
        model_name=model.model_name,
        model_version=model.model_version,
        prediction_type=model.prediction_type,
        status=model.status.value,
        training_data_from=model.training_data_from,
        training_data_to=model.training_data_to,
        metrics=model.metrics or {},
        created_at=model.created_at,
    )
