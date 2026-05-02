from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.core import AssignmentResourceType


class FeatureGenerationRequest(BaseModel):
    event_id: str | None = None
    include_event_feature: bool = True
    include_resource_features: bool = True

    @model_validator(mode="after")
    def validate_payload(self) -> "FeatureGenerationRequest":
        if not self.include_event_feature and not self.include_resource_features:
            raise ValueError(
                "At least one of include_event_feature or include_resource_features must be true."
            )
        if self.include_event_feature and self.event_id is None:
            raise ValueError("event_id is required when include_event_feature is true.")
        return self


class EventFeatureSnapshot(BaseModel):
    event_id: str
    feature_event_type: str | None = None
    feature_event_subtype: str | None = None
    feature_city: str | None = None
    feature_location_type: str | None = None
    feature_attendee_count: int | None = None
    feature_attendee_bucket: str | None = None
    feature_setup_complexity_score: int | None = None
    feature_access_difficulty: int | None = None
    feature_parking_difficulty: int | None = None
    feature_priority: str | None = None
    feature_day_of_week: int | None = None
    feature_month: int | None = None
    feature_season: str | None = None
    feature_requires_transport: bool | None = None
    feature_requires_setup: bool | None = None
    feature_requires_teardown: bool | None = None
    feature_required_person_count: int | None = None
    feature_required_equipment_count: int | None = None
    feature_required_vehicle_count: int | None = None
    feature_estimated_distance_km: Decimal | None = None
    feature_client_priority: str | None = None
    generated_at: datetime


class ResourceFeatureSnapshot(BaseModel):
    resource_feature_id: str
    resource_type: AssignmentResourceType
    person_id: str | None = None
    equipment_id: str | None = None
    vehicle_id: str | None = None
    avg_delay_last_10: Decimal | None = None
    avg_job_duration_variance: Decimal | None = None
    incident_rate_last_30d: Decimal | None = None
    utilization_rate_last_30d: Decimal | None = None
    fatigue_score: Decimal | None = None
    reliability_score: Decimal | None = None
    generated_at: datetime


class FeatureGenerationResponse(BaseModel):
    generated_at: datetime
    event_feature: EventFeatureSnapshot | None = None
    resource_features: list[ResourceFeatureSnapshot] = Field(default_factory=list)
    resource_features_generated: int


class ResourceFeatureListResponse(BaseModel):
    items: list[ResourceFeatureSnapshot] = Field(default_factory=list)
    total: int
