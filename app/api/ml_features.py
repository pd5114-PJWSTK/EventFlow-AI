from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ai import EventFeature, ResourceFeature
from app.schemas.ml_features import (
    EventFeatureSnapshot,
    FeatureGenerationRequest,
    FeatureGenerationResponse,
    ResourceFeatureListResponse,
    ResourceFeatureSnapshot,
)
from app.services.ml_feature_service import (
    FeatureEngineeringError,
    generate_feature_snapshots,
)


router = APIRouter(prefix="/api/ml", tags=["ml"])


@router.post("/features/generate", response_model=FeatureGenerationResponse)
def generate_features_endpoint(
    payload: FeatureGenerationRequest,
    db: Session = Depends(get_db),
) -> FeatureGenerationResponse:
    try:
        result = generate_feature_snapshots(
            db,
            event_id=payload.event_id,
            include_event_feature=payload.include_event_feature,
            include_resource_features=payload.include_resource_features,
        )
        return FeatureGenerationResponse(
            generated_at=result.generated_at,
            event_feature=(
                _event_snapshot(result.event_feature)
                if result.event_feature is not None
                else None
            ),
            resource_features=[
                _resource_snapshot(snapshot) for snapshot in result.resource_features
            ],
            resource_features_generated=len(result.resource_features),
        )
    except FeatureEngineeringError as exc:
        if str(exc) == "Event not found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.get("/features/events/{event_id}", response_model=EventFeatureSnapshot)
def get_event_features_endpoint(
    event_id: str,
    db: Session = Depends(get_db),
) -> EventFeatureSnapshot:
    snapshot = db.get(EventFeature, event_id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event feature snapshot not found"
        )
    return _event_snapshot(snapshot)


@router.get("/features/resources/latest", response_model=ResourceFeatureListResponse)
def list_resource_features_endpoint(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> ResourceFeatureListResponse:
    snapshots = (
        db.query(ResourceFeature)
        .order_by(ResourceFeature.generated_at.desc())
        .limit(limit)
        .all()
    )
    return ResourceFeatureListResponse(
        items=[_resource_snapshot(snapshot) for snapshot in snapshots],
        total=len(snapshots),
    )


def _event_snapshot(feature: EventFeature) -> EventFeatureSnapshot:
    return EventFeatureSnapshot(
        event_id=feature.event_id,
        feature_event_type=feature.feature_event_type,
        feature_event_subtype=feature.feature_event_subtype,
        feature_city=feature.feature_city,
        feature_location_type=feature.feature_location_type,
        feature_attendee_count=feature.feature_attendee_count,
        feature_attendee_bucket=feature.feature_attendee_bucket,
        feature_setup_complexity_score=feature.feature_setup_complexity_score,
        feature_access_difficulty=feature.feature_access_difficulty,
        feature_parking_difficulty=feature.feature_parking_difficulty,
        feature_priority=feature.feature_priority,
        feature_day_of_week=feature.feature_day_of_week,
        feature_month=feature.feature_month,
        feature_season=feature.feature_season,
        feature_requires_transport=feature.feature_requires_transport,
        feature_requires_setup=feature.feature_requires_setup,
        feature_requires_teardown=feature.feature_requires_teardown,
        feature_required_person_count=feature.feature_required_person_count,
        feature_required_equipment_count=feature.feature_required_equipment_count,
        feature_required_vehicle_count=feature.feature_required_vehicle_count,
        feature_estimated_distance_km=feature.feature_estimated_distance_km,
        feature_client_priority=feature.feature_client_priority,
        generated_at=feature.generated_at,
    )


def _resource_snapshot(feature: ResourceFeature) -> ResourceFeatureSnapshot:
    return ResourceFeatureSnapshot(
        resource_feature_id=feature.resource_feature_id,
        resource_type=feature.resource_type,
        person_id=feature.person_id,
        equipment_id=feature.equipment_id,
        vehicle_id=feature.vehicle_id,
        avg_delay_last_10=feature.avg_delay_last_10,
        avg_job_duration_variance=feature.avg_job_duration_variance,
        incident_rate_last_30d=feature.incident_rate_last_30d,
        utilization_rate_last_30d=feature.utilization_rate_last_30d,
        fatigue_score=feature.fatigue_score,
        reliability_score=feature.reliability_score,
        generated_at=feature.generated_at,
    )
