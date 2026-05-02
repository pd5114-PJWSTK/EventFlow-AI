from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.ai import PredictionType


class TrainBaselineModelRequest(BaseModel):
    prediction_type: PredictionType = PredictionType.duration_estimate
    model_name: str = Field(default="event_duration_baseline", min_length=1, max_length=120)
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


class ModelRegistryListResponse(BaseModel):
    items: list[ModelRegistryRead] = Field(default_factory=list)
    total: int
