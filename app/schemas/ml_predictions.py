from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.models.ai import PredictionType


class GeneratePredictionRequest(BaseModel):
    event_id: str
    prediction_type: PredictionType = PredictionType.duration_estimate
    model_id: str | None = None
    assignment_id: str | None = None
    explanation: str | None = None


class PredictionRead(BaseModel):
    prediction_id: str
    event_id: str | None = None
    assignment_id: str | None = None
    model_id: str | None = None
    prediction_type: PredictionType
    predicted_value: Decimal | None = None
    predicted_label: str | None = None
    confidence_score: Decimal | None = None
    explanation: str | None = None
    feature_snapshot: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime


class GeneratePredictionResponse(BaseModel):
    prediction: PredictionRead
    model_name: str | None = None
    model_version: str | None = None


class EvaluatePredictionRequest(BaseModel):
    actual_numeric_value: Decimal | None = None
    actual_label: str | None = None
    notes: str | None = None
    auto_resolve_actual: bool = False

    @model_validator(mode="after")
    def validate_payload(self) -> "EvaluatePredictionRequest":
        if not self.auto_resolve_actual and self.actual_numeric_value is None and self.actual_label is None:
            raise ValueError(
                "Provide actual_numeric_value or actual_label, or set auto_resolve_actual=true."
            )
        return self


class PredictionOutcomeRead(BaseModel):
    prediction_outcome_id: str
    prediction_id: str
    actual_numeric_value: Decimal | None = None
    actual_label: str | None = None
    evaluated_at: datetime
    error_value: Decimal | None = None
    notes: str | None = None


class EvaluatePredictionResponse(BaseModel):
    prediction: PredictionRead
    outcome: PredictionOutcomeRead


class PredictionListResponse(BaseModel):
    items: list[PredictionRead] = Field(default_factory=list)
    total: int
