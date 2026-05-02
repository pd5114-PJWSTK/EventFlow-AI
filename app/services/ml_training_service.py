from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from random import Random
from statistics import mean
from typing import Any

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
class HardenDurationModelResult:
    model: ModelRegistryRead
    trained_samples: int
    backend: str
    artifact_path: str | None
    real_samples_used: int
    train_samples: int
    test_samples: int
    selected_algorithm: str
    validation_summary: dict[str, Any]


@dataclass
class RetrainDurationModelResult:
    model: ModelRegistryRead
    trained_samples: int
    backend: str
    artifact_path: str | None
    activated: bool
    decision_reason: str
    previous_active_model_id: str | None = None


@dataclass
class _TrainingSample:
    event_id: str
    x: list[float]
    y: float
    observed_at: datetime
    is_synthetic: bool = False


def train_baseline_model(
    db: Session,
    *,
    payload: TrainBaselineModelRequest,
) -> TrainBaselineModelResult:
    if payload.prediction_type != PredictionType.duration_estimate:
        raise ModelTrainingError(
            "Only duration_estimate baseline training is supported in phase-7-cp-02."
        )

    settings = get_settings()
    samples, feature_names, real_sample_count = _collect_duration_training_samples(
        db,
        synthetic_samples_per_real=settings.ml_synthetic_samples_per_real,
        random_seed=settings.ml_training_random_seed,
    )
    if real_sample_count < 1:
        raise ModelTrainingError(
            "No training samples found. Generate event features and runtime timings first."
        )
    augmented_sample_count = max(len(samples) - real_sample_count, 0)

    backend = "heuristic_mean_regressor"
    artifact_payload: dict = {}
    predictions: list[float]
    y_values = [sample.y for sample in samples]
    model_selection: dict[str, Any] | None = None

    sklearn_result = _try_train_sklearn(
        samples=samples,
        feature_names=feature_names,
        test_split_ratio=settings.ml_train_test_split_ratio,
        random_seed=settings.ml_training_random_seed,
    )
    if sklearn_result is not None and real_sample_count >= settings.ml_min_training_samples:
        backend = "sklearn_multi_algorithm_selector"
        artifact_payload = sklearn_result["artifact"]
        predictions = sklearn_result["predictions"]
        model_selection = sklearn_result["model_selection"]
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
    metrics["dataset"] = {
        "real_samples": real_sample_count,
        "augmented_samples": augmented_sample_count,
        "total_samples": len(samples),
        "synthetic_samples_per_real": settings.ml_synthetic_samples_per_real,
    }
    if model_selection is not None:
        metrics["model_selection"] = model_selection

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


def harden_duration_model(
    db: Session,
    *,
    model_name: str = "event_duration_hardened",
    activate_model: bool = True,
    required_real_samples: int | None = None,
    train_samples: int | None = None,
    test_samples: int | None = None,
    random_seed: int | None = None,
) -> HardenDurationModelResult:
    settings = get_settings()
    required = (
        required_real_samples
        if required_real_samples is not None
        else settings.ml_hardening_required_real_samples
    )
    train_size = (
        train_samples
        if train_samples is not None
        else settings.ml_hardening_train_samples
    )
    test_size = (
        test_samples
        if test_samples is not None
        else settings.ml_hardening_test_samples
    )
    seed = random_seed if random_seed is not None else settings.ml_training_random_seed

    if train_size + test_size != required:
        raise ModelTrainingError(
            "Invalid hardening split: train_samples + test_samples must equal required_real_samples."
        )

    real_samples, feature_names = _collect_real_duration_training_samples(db)
    if len(real_samples) < required:
        raise ModelTrainingError(
            f"Insufficient real samples for hardening. Required={required}, available={len(real_samples)}."
        )

    selected = sorted(real_samples, key=lambda sample: sample.observed_at)[-required:]
    validation_summary = _validate_hardening_dataset(
        selected_samples=selected,
        required_real_samples=required,
        train_samples=train_size,
        test_samples=test_size,
    )
    if not validation_summary["is_valid"]:
        raise ModelTrainingError("Hardening dataset validation failed.")

    train_set = selected[:train_size]
    test_set = selected[train_size : train_size + test_size]
    hardened_result = _train_and_tune_with_fixed_holdout(
        train_samples=train_set,
        test_samples=test_set,
        feature_names=feature_names,
        random_seed=seed,
    )

    y_values = [sample.y for sample in selected]
    metrics = _build_metrics(
        y_true=y_values,
        y_pred=hardened_result["predictions"],
        sample_count=len(selected),
        backend="sklearn_hardened_duration_model",
        feature_names=feature_names,
    )
    metrics["dataset"] = {
        "real_samples": len(selected),
        "augmented_samples": 0,
        "total_samples": len(selected),
        "split_strategy": "time_ordered_holdout",
        "train_samples": len(train_set),
        "test_samples": len(test_set),
    }
    metrics["dataset_validation"] = validation_summary
    metrics["model_selection"] = hardened_result["model_selection"]
    metrics["hyperparameter_tuning"] = hardened_result["hyperparameter_tuning"]

    version = datetime.now(UTC).strftime("v%Y%m%d%H%M%S")
    if activate_model:
        (
            db.query(ModelRegistry)
            .filter(
                ModelRegistry.model_name == model_name,
                ModelRegistry.prediction_type == PredictionType.duration_estimate,
                ModelRegistry.status == ModelStatus.active,
            )
            .update({ModelRegistry.status: ModelStatus.deprecated}, synchronize_session=False)
        )

    model = ModelRegistry(
        model_name=model_name,
        model_version=version,
        prediction_type=PredictionType.duration_estimate,
        status=ModelStatus.active if activate_model else ModelStatus.training,
        training_data_from=min(sample.observed_at for sample in selected),
        training_data_to=max(sample.observed_at for sample in selected),
        metrics=metrics,
    )
    db.add(model)
    db.flush()

    artifact_path = _save_model_artifact(
        model_name=model_name,
        model_version=version,
        model_id=model.model_id,
        prediction_type=PredictionType.duration_estimate.value,
        backend="sklearn_hardened_duration_model",
        feature_names=feature_names,
        metrics=metrics,
        artifact_payload=hardened_result["artifact"],
    )

    model.metrics = {**model.metrics, "artifact_path": artifact_path}
    db.commit()
    db.refresh(model)

    return HardenDurationModelResult(
        model=_to_model_read(model),
        trained_samples=len(selected),
        backend="sklearn_hardened_duration_model",
        artifact_path=artifact_path,
        real_samples_used=len(selected),
        train_samples=len(train_set),
        test_samples=len(test_set),
        selected_algorithm=str(hardened_result["model_selection"]["selected_algorithm"]),
        validation_summary=validation_summary,
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


def retrain_duration_model(
    db: Session,
    *,
    model_name: str = "event_duration_baseline",
    min_samples_required: int | None = None,
    min_r2_improvement: float | None = None,
    max_mae_ratio: float | None = None,
) -> RetrainDurationModelResult:
    settings = get_settings()
    effective_min_samples = (
        min_samples_required
        if min_samples_required is not None
        else settings.ml_retrain_activation_min_samples
    )
    effective_min_r2_improvement = (
        min_r2_improvement
        if min_r2_improvement is not None
        else settings.ml_retrain_activation_min_r2_improvement
    )
    effective_max_mae_ratio = (
        max_mae_ratio
        if max_mae_ratio is not None
        else settings.ml_retrain_activation_max_mae_ratio
    )

    baseline_active = (
        db.query(ModelRegistry)
        .filter(
            ModelRegistry.model_name == model_name,
            ModelRegistry.prediction_type == PredictionType.duration_estimate,
            ModelRegistry.status == ModelStatus.active,
        )
        .order_by(ModelRegistry.created_at.desc())
        .first()
    )

    candidate = train_baseline_model(
        db,
        payload=TrainBaselineModelRequest(
            prediction_type=PredictionType.duration_estimate,
            model_name=model_name,
            activate_model=False,
        ),
    )

    candidate_db = db.get(ModelRegistry, candidate.model.model_id)
    if candidate_db is None:
        raise ModelTrainingError("Candidate model not found after training.")

    activation = _evaluate_activation(
        candidate_model=candidate_db,
        baseline_active=baseline_active,
        min_samples_required=effective_min_samples,
        min_r2_improvement=effective_min_r2_improvement,
        max_mae_ratio=effective_max_mae_ratio,
    )

    if activation["activate"]:
        if baseline_active is not None:
            baseline_active.status = ModelStatus.deprecated
        candidate_db.status = ModelStatus.active
    else:
        candidate_db.status = ModelStatus.deprecated

    candidate_db.metrics = {
        **(candidate_db.metrics or {}),
        "activation_decision": {
            "activated": activation["activate"],
            "reason": activation["reason"],
            "min_samples_required": effective_min_samples,
            "min_r2_improvement": effective_min_r2_improvement,
            "max_mae_ratio": effective_max_mae_ratio,
            "evaluated_at": datetime.now(UTC).isoformat(),
            "baseline_model_id": baseline_active.model_id if baseline_active else None,
        },
    }
    db.commit()
    db.refresh(candidate_db)

    return RetrainDurationModelResult(
        model=_to_model_read(candidate_db),
        trained_samples=candidate.trained_samples,
        backend=candidate.backend,
        artifact_path=candidate.artifact_path,
        activated=bool(activation["activate"]),
        decision_reason=str(activation["reason"]),
        previous_active_model_id=baseline_active.model_id if baseline_active else None,
    )


def _collect_duration_training_samples(
    db: Session,
    *,
    synthetic_samples_per_real: int,
    random_seed: int,
) -> tuple[list[_TrainingSample], list[str], int]:
    real_samples, feature_names = _collect_real_duration_training_samples(db)
    synthetic_samples = _augment_duration_samples(
        real_samples=real_samples,
        synthetic_samples_per_real=synthetic_samples_per_real,
        random_seed=random_seed,
    )
    return (
        real_samples + synthetic_samples,
        feature_names,
        len(real_samples),
    )


def _collect_real_duration_training_samples(
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
    real_samples: list[_TrainingSample] = []

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
        real_samples.append(
            _TrainingSample(
                event_id=feature.event_id,
                x=x_vector,
                y=float(actual_minutes),
                observed_at=observed_time,
                is_synthetic=False,
            )
        )
    return real_samples, feature_names


def _try_train_sklearn(
    *,
    samples: list[_TrainingSample],
    feature_names: list[str],
    test_split_ratio: float,
    random_seed: int,
) -> dict | None:
    try:
        from sklearn.model_selection import train_test_split
    except Exception:
        return None

    x_values = [sample.x for sample in samples]
    y_values = [sample.y for sample in samples]

    test_count = _resolve_test_count(len(samples), test_split_ratio)
    if test_count <= 0 or test_count >= len(samples):
        return None

    x_train, x_test, y_train, y_test = train_test_split(
        x_values,
        y_values,
        test_size=test_count,
        random_state=random_seed,
    )

    candidates = _candidate_model_specs()
    evaluated = _evaluate_candidates(
        candidates=candidates,
        x_train=x_train,
        y_train=y_train,
        x_test=x_test,
        y_test=y_test,
        random_seed=random_seed,
    )

    if not evaluated:
        return None
    winner = evaluated[0]
    y_pred = _predict_non_negative(winner["estimator"], x_values)
    model_selection = {
        "selected_algorithm": winner["name"],
        "train_samples": len(y_train),
        "test_samples": len(y_test),
        "split_strategy": "holdout",
        "test_split_ratio": round(len(y_test) / len(samples), 4),
        "random_seed": random_seed,
        "leaderboard": [
            {
                "algorithm": item["name"],
                "params": item["params"],
                "train_metrics": item["train_metrics"],
                "test_metrics": item["test_metrics"],
            }
            for item in evaluated
        ],
    }

    return {
        "predictions": y_pred,
        "model_selection": model_selection,
        "artifact": {
            "kind": "sklearn_estimator",
            "algorithm": winner["name"],
            "feature_names": feature_names,
            "model": winner["estimator"],
            "model_selection": model_selection,
        },
    }


def _train_and_tune_with_fixed_holdout(
    *,
    train_samples: list[_TrainingSample],
    test_samples: list[_TrainingSample],
    feature_names: list[str],
    random_seed: int,
) -> dict[str, Any]:
    x_train = [sample.x for sample in train_samples]
    y_train = [sample.y for sample in train_samples]
    x_test = [sample.x for sample in test_samples]
    y_test = [sample.y for sample in test_samples]
    x_all = x_train + x_test

    if not x_train or not x_test:
        raise ModelTrainingError("Hardening requires non-empty train and test sets.")

    baseline_candidates = _candidate_model_specs()
    baseline_results = _evaluate_candidates(
        candidates=baseline_candidates,
        x_train=x_train,
        y_train=y_train,
        x_test=x_test,
        y_test=y_test,
        random_seed=random_seed,
    )
    if not baseline_results:
        raise ModelTrainingError("Unable to train baseline candidates for hardening.")

    baseline_winner = baseline_results[0]
    winner_algorithm = str(baseline_winner["name"])

    tuned_results = _tune_best_algorithm(
        algorithm=winner_algorithm,
        x_train=x_train,
        y_train=y_train,
        x_test=x_test,
        y_test=y_test,
        random_seed=random_seed,
    )
    tuned_winner = tuned_results["winner"]
    tuned_estimator = tuned_winner["estimator"]
    tuned_estimator.fit(x_train, y_train)
    y_all_pred = _predict_non_negative(tuned_estimator, x_all)

    model_selection = {
        "selected_algorithm": winner_algorithm,
        "train_samples": len(train_samples),
        "test_samples": len(test_samples),
        "split_strategy": "time_ordered_holdout",
        "test_split_ratio": round(len(test_samples) / len(x_all), 4),
        "random_seed": random_seed,
        "leaderboard": [
            {
                "algorithm": item["name"],
                "params": item["params"],
                "train_metrics": item["train_metrics"],
                "test_metrics": item["test_metrics"],
            }
            for item in baseline_results
        ],
    }
    hyperparameter_tuning = {
        "algorithm": winner_algorithm,
        "winning_params": tuned_winner["params"],
        "trials": [
            {
                "params": item["params"],
                "train_metrics": item["train_metrics"],
                "test_metrics": item["test_metrics"],
            }
            for item in tuned_results["trials"]
        ],
    }

    artifact = {
        "kind": "sklearn_estimator",
        "algorithm": winner_algorithm,
        "feature_names": feature_names,
        "model": tuned_estimator,
        "model_selection": model_selection,
        "hyperparameter_tuning": hyperparameter_tuning,
    }
    return {
        "predictions": y_all_pred,
        "artifact": artifact,
        "model_selection": model_selection,
        "hyperparameter_tuning": hyperparameter_tuning,
    }


def _candidate_model_specs() -> list[dict[str, Any]]:
    return [
        {"name": "linear_regression", "params": {}},
        {"name": "ridge_regression", "params": {"alpha": 1.0}},
        {
            "name": "random_forest",
            "params": {
                "n_estimators": 300,
                "max_depth": 12,
                "min_samples_leaf": 2,
            },
        },
        {
            "name": "gradient_boosting",
            "params": {
                "n_estimators": 400,
                "learning_rate": 0.05,
                "max_depth": 3,
                "subsample": 0.9,
            },
        },
    ]


def _evaluate_candidates(
    *,
    candidates: list[dict[str, Any]],
    x_train: list[list[float]],
    y_train: list[float],
    x_test: list[list[float]],
    y_test: list[float],
    random_seed: int,
) -> list[dict[str, Any]]:
    evaluated: list[dict[str, Any]] = []
    for candidate in candidates:
        try:
            estimator = _build_estimator(
                algorithm=str(candidate["name"]),
                params=dict(candidate.get("params", {})),
                random_seed=random_seed,
            )
            estimator.fit(x_train, y_train)
            train_pred = _predict_non_negative(estimator, x_train)
            test_pred = _predict_non_negative(estimator, x_test)
        except Exception:
            continue

        evaluated.append(
            {
                "name": candidate["name"],
                "params": candidate["params"],
                "estimator": estimator,
                "train_metrics": _regression_metrics(y_true=y_train, y_pred=train_pred),
                "test_metrics": _regression_metrics(y_true=y_test, y_pred=test_pred),
            }
        )

    evaluated.sort(
        key=lambda item: (
            item["test_metrics"]["mae_minutes"],
            item["test_metrics"]["rmse_minutes"],
            -item["test_metrics"]["r2"],
        )
    )
    return evaluated


def _tune_best_algorithm(
    *,
    algorithm: str,
    x_train: list[list[float]],
    y_train: list[float],
    x_test: list[list[float]],
    y_test: list[float],
    random_seed: int,
) -> dict[str, Any]:
    param_grid = _tuning_param_grid(algorithm)
    trials: list[dict[str, Any]] = []
    for params in param_grid:
        estimator = _build_estimator(
            algorithm=algorithm,
            params=params,
            random_seed=random_seed,
        )
        try:
            estimator.fit(x_train, y_train)
            train_pred = _predict_non_negative(estimator, x_train)
            test_pred = _predict_non_negative(estimator, x_test)
        except Exception:
            continue

        trials.append(
            {
                "params": params,
                "estimator": estimator,
                "train_metrics": _regression_metrics(y_true=y_train, y_pred=train_pred),
                "test_metrics": _regression_metrics(y_true=y_test, y_pred=test_pred),
            }
        )

    if not trials:
        raise ModelTrainingError("Hyperparameter tuning failed for the selected algorithm.")

    trials.sort(
        key=lambda item: (
            item["test_metrics"]["mae_minutes"],
            item["test_metrics"]["rmse_minutes"],
            -item["test_metrics"]["r2"],
        )
    )
    return {"winner": trials[0], "trials": trials}


def _build_estimator(algorithm: str, params: dict[str, Any], random_seed: int) -> Any:
    from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
    from sklearn.linear_model import LinearRegression, Ridge
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    if algorithm == "linear_regression":
        return Pipeline(
            steps=[
                ("scaler", StandardScaler()),
                ("model", LinearRegression()),
            ]
        )
    if algorithm == "ridge_regression":
        alpha = float(params.get("alpha", 1.0))
        return Pipeline(
            steps=[
                ("scaler", StandardScaler()),
                ("model", Ridge(alpha=alpha)),
            ]
        )
    if algorithm == "random_forest":
        return RandomForestRegressor(
            n_estimators=int(params.get("n_estimators", 300)),
            max_depth=int(params.get("max_depth", 12)),
            min_samples_leaf=int(params.get("min_samples_leaf", 2)),
            random_state=random_seed,
            n_jobs=1,
        )
    if algorithm == "gradient_boosting":
        return GradientBoostingRegressor(
            n_estimators=int(params.get("n_estimators", 400)),
            learning_rate=float(params.get("learning_rate", 0.05)),
            max_depth=int(params.get("max_depth", 3)),
            subsample=float(params.get("subsample", 0.9)),
            random_state=random_seed,
        )
    raise ModelTrainingError(f"Unsupported algorithm for estimator build: {algorithm}")


def _tuning_param_grid(algorithm: str) -> list[dict[str, Any]]:
    if algorithm == "gradient_boosting":
        return [
            {"n_estimators": 200, "learning_rate": 0.05, "max_depth": 2, "subsample": 0.85},
            {"n_estimators": 300, "learning_rate": 0.05, "max_depth": 3, "subsample": 0.9},
            {"n_estimators": 500, "learning_rate": 0.03, "max_depth": 3, "subsample": 0.9},
            {"n_estimators": 400, "learning_rate": 0.04, "max_depth": 4, "subsample": 0.95},
        ]
    if algorithm == "random_forest":
        return [
            {"n_estimators": 200, "max_depth": 10, "min_samples_leaf": 2},
            {"n_estimators": 400, "max_depth": 14, "min_samples_leaf": 1},
            {"n_estimators": 500, "max_depth": 12, "min_samples_leaf": 2},
        ]
    if algorithm == "ridge_regression":
        return [{"alpha": 0.2}, {"alpha": 1.0}, {"alpha": 2.0}, {"alpha": 5.0}]
    if algorithm == "linear_regression":
        return [{}]
    raise ModelTrainingError(f"Unsupported algorithm for tuning: {algorithm}")


def _validate_hardening_dataset(
    *,
    selected_samples: list[_TrainingSample],
    required_real_samples: int,
    train_samples: int,
    test_samples: int,
) -> dict[str, Any]:
    duplicate_event_count = len(selected_samples) - len({item.event_id for item in selected_samples})
    invalid_target_count = sum(1 for item in selected_samples if item.y <= 0)
    invalid_feature_count = 0
    for sample in selected_samples:
        feature_checks = [
            0 <= sample.x[1] <= 10,
            0 <= sample.x[2] <= 10,
            0 <= sample.x[3] <= 10,
            1 <= sample.x[7] <= 4,
            1 <= sample.x[8] <= 7,
            1 <= sample.x[9] <= 12,
            0 <= sample.x[10] <= 4,
        ]
        if not all(feature_checks):
            invalid_feature_count += 1

    issues: list[str] = []
    if len(selected_samples) != required_real_samples:
        issues.append("sample_count_mismatch")
    if duplicate_event_count > 0:
        issues.append("duplicate_events_detected")
    if invalid_target_count > 0:
        issues.append("invalid_target_values")
    if invalid_feature_count > 0:
        issues.append("invalid_feature_values")
    if train_samples + test_samples != required_real_samples:
        issues.append("split_mismatch")

    return {
        "is_valid": len(issues) == 0,
        "issues": issues,
        "sample_count": len(selected_samples),
        "required_real_samples": required_real_samples,
        "duplicate_event_count": duplicate_event_count,
        "invalid_target_count": invalid_target_count,
        "invalid_feature_count": invalid_feature_count,
        "train_samples": train_samples,
        "test_samples": test_samples,
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


def _augment_duration_samples(
    *,
    real_samples: list[_TrainingSample],
    synthetic_samples_per_real: int,
    random_seed: int,
) -> list[_TrainingSample]:
    if synthetic_samples_per_real <= 0 or not real_samples:
        return []

    rng = Random(random_seed)
    synthetic: list[_TrainingSample] = []
    for sample in real_samples:
        for _ in range(synthetic_samples_per_real):
            x_aug = _augment_feature_vector(sample.x, rng)
            y_aug = _augment_target_minutes(
                base_minutes=sample.y,
                base_features=sample.x,
                augmented_features=x_aug,
                rng=rng,
            )
            synthetic.append(
                _TrainingSample(
                    event_id=sample.event_id,
                    x=x_aug,
                    y=y_aug,
                    observed_at=sample.observed_at,
                    is_synthetic=True,
                )
            )
    return synthetic


def _augment_feature_vector(base_x: list[float], rng: Random) -> list[float]:
    attendee = float(max(10, int(round(base_x[0] * rng.uniform(0.75, 1.35)))))
    setup = float(int(_clamp(round(base_x[1] + rng.randint(-1, 1)), 0, 10)))
    access = float(int(_clamp(round(base_x[2] + rng.randint(-1, 1)), 0, 10)))
    parking = float(int(_clamp(round(base_x[3] + rng.randint(-1, 1)), 0, 10)))
    req_people = float(max(0, int(round(base_x[4] + rng.randint(-1, 2)))))
    req_equipment = float(max(0, int(round(base_x[5] + rng.randint(-1, 2)))))
    req_vehicle = float(max(0, int(round(base_x[6] + rng.randint(-1, 1)))))
    priority = float(int(_clamp(round(base_x[7] + rng.choice([-1, 0, 0, 1])), 1, 4)))
    day = float(int(_clamp(round(base_x[8] + rng.choice([-1, 0, 1])), 1, 7)))
    month = float(int(_clamp(round(base_x[9] + rng.choice([-1, 0, 1])), 1, 12)))
    season = float(int(_clamp(round(base_x[10] + rng.choice([-1, 0, 1])), 1, 4)))

    transport = base_x[11]
    if rng.random() < 0.08:
        transport = 0.0 if base_x[11] > 0 else 1.0

    setup_required = base_x[12]
    if rng.random() < 0.06:
        setup_required = 0.0 if base_x[12] > 0 else 1.0

    teardown_required = base_x[13]
    if rng.random() < 0.06:
        teardown_required = 0.0 if base_x[13] > 0 else 1.0

    return [
        attendee,
        setup,
        access,
        parking,
        req_people,
        req_equipment,
        req_vehicle,
        priority,
        day,
        month,
        season,
        transport,
        setup_required,
        teardown_required,
    ]


def _augment_target_minutes(
    *,
    base_minutes: float,
    base_features: list[float],
    augmented_features: list[float],
    rng: Random,
) -> float:
    attendee_delta = (augmented_features[0] - base_features[0]) / max(base_features[0], 60.0)
    complexity_delta = (
        (augmented_features[1] - base_features[1]) * 0.04
        + (augmented_features[2] - base_features[2]) * 0.03
        + (augmented_features[3] - base_features[3]) * 0.02
    )
    requirements_delta = (
        (augmented_features[4] - base_features[4]) * 0.02
        + (augmented_features[5] - base_features[5]) * 0.02
        + (augmented_features[6] - base_features[6]) * 0.03
    )
    flags_delta = (
        (augmented_features[11] - base_features[11]) * 0.06
        + (augmented_features[12] - base_features[12]) * 0.08
        + (augmented_features[13] - base_features[13]) * 0.05
    )
    season_delta = (augmented_features[10] - base_features[10]) * 0.015
    noise = rng.uniform(-0.08, 0.08)

    multiplier = 1 + (attendee_delta * 0.35) + complexity_delta + requirements_delta + flags_delta + season_delta + noise
    minutes = base_minutes * max(multiplier, 0.35)
    return float(_clamp(minutes, 30.0, 720.0))


def _resolve_test_count(total_samples: int, requested_ratio: float) -> int:
    if total_samples < 5:
        return max(1, total_samples // 3)
    ratio = _clamp(requested_ratio, 0.15, 0.35)
    test_count = int(round(total_samples * ratio))
    test_count = max(test_count, 2)
    test_count = min(test_count, total_samples - 2)
    return test_count


def _predict_non_negative(estimator: Any, x_values: list[list[float]]) -> list[float]:
    predicted = estimator.predict(x_values)
    return [float(max(value, 0.0)) for value in predicted]


def _regression_metrics(*, y_true: list[float], y_pred: list[float]) -> dict[str, float]:
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
        "mae_minutes": round(mae, 4),
        "rmse_minutes": round(rmse, 4),
        "r2": round(r2, 6),
    }


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(value, max_value))


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


def _evaluate_activation(
    *,
    candidate_model: ModelRegistry,
    baseline_active: ModelRegistry | None,
    min_samples_required: int,
    min_r2_improvement: float,
    max_mae_ratio: float,
) -> dict[str, bool | str]:
    candidate_metrics = candidate_model.metrics or {}
    candidate_samples = int(candidate_metrics.get("sample_count", 0))
    if candidate_samples < min_samples_required:
        return {
            "activate": False,
            "reason": "insufficient_samples",
        }

    if baseline_active is None:
        return {
            "activate": True,
            "reason": "activated_no_baseline",
        }

    baseline_metrics = baseline_active.metrics or {}
    candidate_r2 = float(candidate_metrics.get("r2", 0.0))
    baseline_r2 = float(baseline_metrics.get("r2", 0.0))
    candidate_mae = float(candidate_metrics.get("mae_minutes", 0.0))
    baseline_mae = float(baseline_metrics.get("mae_minutes", 0.0))

    required_r2 = baseline_r2 + float(min_r2_improvement)
    mae_limit = baseline_mae * float(max_mae_ratio)

    if candidate_r2 < required_r2:
        return {
            "activate": False,
            "reason": "r2_below_threshold",
        }
    if baseline_mae > 0 and candidate_mae > mae_limit:
        return {
            "activate": False,
            "reason": "mae_above_threshold",
        }

    return {
        "activate": True,
        "reason": "activated_metrics_improved",
    }


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
