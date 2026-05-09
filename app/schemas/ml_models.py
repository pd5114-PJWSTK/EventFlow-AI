from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.ai import PredictionType

MODEL_NAME_PATTERN = r"^[A-Za-z0-9_-]{1,120}$"


class TrainBaselineModelRequest(BaseModel):
    prediction_type: PredictionType = PredictionType.duration_estimate
    model_name: str = Field(
        default="event_duration_baseline",
        min_length=1,
        max_length=120,
        pattern=MODEL_NAME_PATTERN,
    )
    activate_model: bool = True


class ModelRegistryRead(BaseModel):
    model_id: str
    model_name: str
    model_version: str
    prediction_type: PredictionType
    status: str
    training_data_from: datetime | None = None
    training_data_to: datetime | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class TrainBaselineModelResponse(BaseModel):
    model: ModelRegistryRead
    trained_samples: int
    backend: str
    artifact_path: str | None = None


class HardenDurationModelRequest(BaseModel):
    model_name: str = Field(
        default="event_duration_hardened",
        min_length=1,
        max_length=120,
        pattern=MODEL_NAME_PATTERN,
    )
    activate_model: bool = True
    required_real_samples: int | None = Field(default=None, ge=10)
    train_samples: int | None = Field(default=None, ge=1)
    test_samples: int | None = Field(default=None, ge=1)
    random_seed: int | None = None


class HardenDurationModelResponse(BaseModel):
    model: ModelRegistryRead
    trained_samples: int
    backend: str
    artifact_path: str | None = None
    real_samples_used: int
    train_samples: int
    test_samples: int
    selected_algorithm: str
    validation_summary: dict[str, Any] = Field(default_factory=dict)


class TrainPlanEvaluatorRequest(BaseModel):
    model_name: str = Field(
        default="plan_candidate_evaluator",
        min_length=1,
        max_length=120,
        pattern=MODEL_NAME_PATTERN,
    )
    activate_model: bool = True
    required_real_samples: int = Field(default=60, ge=20, le=1000)
    random_seed: int | None = None


class TrainPlanEvaluatorResponse(BaseModel):
    model: ModelRegistryRead
    trained_samples: int
    backend: str
    artifact_path: str | None = None
    real_samples_used: int
    candidate_samples: int
    selected_algorithm: str


class RetrainDurationModelRequest(BaseModel):
    model_name: str = Field(
        default="event_duration_baseline",
        min_length=1,
        max_length=120,
        pattern=MODEL_NAME_PATTERN,
    )
    min_samples_required: int | None = Field(default=None, ge=1)
    min_r2_improvement: float | None = None
    max_mae_ratio: float | None = Field(default=None, gt=0)
    force_activate: bool = False


class RetrainDurationModelResponse(BaseModel):
    model: ModelRegistryRead
    trained_samples: int
    backend: str
    artifact_path: str | None = None
    activated: bool
    decision_reason: str
    previous_active_model_id: str | None = None


class ModelRegistryListResponse(BaseModel):
    items: list[ModelRegistryRead] = Field(default_factory=list)
    total: int
