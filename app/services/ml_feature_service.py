from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from math import ceil

from sqlalchemy.orm import Session, joinedload

from app.models.ai import EventFeature, ResourceFeature
from app.models.core import (
    Assignment,
    AssignmentResourceType,
    Event,
    RequirementType,
    ResourcePerson,
    Equipment,
    Vehicle,
)
from app.models.ops import ActualTiming, Incident


class FeatureEngineeringError(ValueError):
    pass


@dataclass
class FeatureGenerationResult:
    generated_at: datetime
    event_feature: EventFeature | None = None
    resource_features: list[ResourceFeature] = field(default_factory=list)


def generate_feature_snapshots(
    db: Session,
    *,
    event_id: str | None,
    include_event_feature: bool = True,
    include_resource_features: bool = True,
) -> FeatureGenerationResult:
    generated_at = datetime.now(UTC)

    if include_event_feature and event_id is None:
        raise FeatureEngineeringError(
            "event_id is required when include_event_feature is true"
        )

    event_feature: EventFeature | None = None
    if include_event_feature and event_id is not None:
        event_feature = upsert_event_feature_snapshot(
            db, event_id=event_id, generated_at=generated_at
        )

    resource_features: list[ResourceFeature] = []
    if include_resource_features:
        resource_features = generate_resource_feature_snapshots(
            db, generated_at=generated_at
        )

    db.commit()

    if event_feature is not None:
        db.refresh(event_feature)
    for snapshot in resource_features:
        db.refresh(snapshot)

    return FeatureGenerationResult(
        generated_at=generated_at,
        event_feature=event_feature,
        resource_features=resource_features,
    )


def upsert_event_feature_snapshot(
    db: Session, *, event_id: str, generated_at: datetime | None = None
) -> EventFeature:
    event = (
        db.query(Event)
        .options(
            joinedload(Event.client),
            joinedload(Event.location),
            joinedload(Event.requirements),
            joinedload(Event.transport_legs),
        )
        .filter(Event.event_id == event_id)
        .one_or_none()
    )
    if event is None:
        raise FeatureEngineeringError("Event not found")

    person_requirements = 0
    equipment_requirements = 0
    vehicle_requirements = 0

    for requirement in event.requirements:
        quantity = _quantity_to_int(requirement.quantity)
        if requirement.requirement_type in (
            RequirementType.person_role,
            RequirementType.person_skill,
        ):
            person_requirements += quantity
        elif requirement.requirement_type == RequirementType.equipment_type:
            equipment_requirements += quantity
        elif requirement.requirement_type == RequirementType.vehicle_type:
            vehicle_requirements += quantity

    estimated_distance_values = [
        leg.estimated_distance_km
        for leg in event.transport_legs
        if leg.estimated_distance_km is not None
    ]
    avg_distance = None
    if estimated_distance_values:
        avg_distance = _avg_decimal(
            [Decimal(value) for value in estimated_distance_values], places="0.01"
        )

    feature = db.get(EventFeature, event.event_id)
    if feature is None:
        feature = EventFeature(event_id=event.event_id)
        db.add(feature)

    planned_start = event.planned_start
    month = planned_start.month

    feature.feature_event_type = event.event_type
    feature.feature_event_subtype = event.event_subtype
    feature.feature_city = event.location.city if event.location is not None else None
    feature.feature_location_type = (
        event.location.location_type.value if event.location is not None else None
    )
    feature.feature_attendee_count = event.attendee_count
    feature.feature_attendee_bucket = _attendee_bucket(event.attendee_count)
    feature.feature_setup_complexity_score = (
        event.location.setup_complexity_score if event.location is not None else None
    )
    feature.feature_access_difficulty = (
        event.location.access_difficulty if event.location is not None else None
    )
    feature.feature_parking_difficulty = (
        event.location.parking_difficulty if event.location is not None else None
    )
    feature.feature_priority = event.priority.value
    feature.feature_day_of_week = planned_start.isoweekday()
    feature.feature_month = month
    feature.feature_season = _season_from_month(month)
    feature.feature_requires_transport = event.requires_transport
    feature.feature_requires_setup = event.requires_setup
    feature.feature_requires_teardown = event.requires_teardown
    feature.feature_required_person_count = person_requirements
    feature.feature_required_equipment_count = equipment_requirements
    feature.feature_required_vehicle_count = vehicle_requirements
    feature.feature_estimated_distance_km = avg_distance
    feature.feature_client_priority = (
        event.client.priority.value if event.client is not None else None
    )
    feature.generated_at = generated_at or datetime.now(UTC)

    return feature


def generate_resource_feature_snapshots(
    db: Session, *, generated_at: datetime | None = None
) -> list[ResourceFeature]:
    snapshot_time = generated_at or datetime.now(UTC)
    snapshots: list[ResourceFeature] = []

    people = db.query(ResourcePerson).filter(ResourcePerson.active.is_(True)).all()
    for person in people:
        metrics = _calculate_resource_metrics(
            db,
            resource_type=AssignmentResourceType.person,
            resource_id=person.person_id,
            generated_at=snapshot_time,
            max_daily_hours=person.max_daily_hours,
        )
        snapshot = ResourceFeature(
            resource_type=AssignmentResourceType.person,
            person_id=person.person_id,
            avg_delay_last_10=metrics.avg_delay_last_10,
            avg_job_duration_variance=metrics.avg_job_duration_variance,
            incident_rate_last_30d=metrics.incident_rate_last_30d,
            utilization_rate_last_30d=metrics.utilization_rate_last_30d,
            fatigue_score=metrics.fatigue_score,
            reliability_score=metrics.reliability_score,
            generated_at=snapshot_time,
        )
        db.add(snapshot)
        snapshots.append(snapshot)

    equipment_items = db.query(Equipment).filter(Equipment.active.is_(True)).all()
    for equipment in equipment_items:
        metrics = _calculate_resource_metrics(
            db,
            resource_type=AssignmentResourceType.equipment,
            resource_id=equipment.equipment_id,
            generated_at=snapshot_time,
        )
        snapshot = ResourceFeature(
            resource_type=AssignmentResourceType.equipment,
            equipment_id=equipment.equipment_id,
            avg_delay_last_10=metrics.avg_delay_last_10,
            avg_job_duration_variance=metrics.avg_job_duration_variance,
            incident_rate_last_30d=metrics.incident_rate_last_30d,
            utilization_rate_last_30d=metrics.utilization_rate_last_30d,
            fatigue_score=metrics.fatigue_score,
            reliability_score=metrics.reliability_score,
            generated_at=snapshot_time,
        )
        db.add(snapshot)
        snapshots.append(snapshot)

    vehicles = db.query(Vehicle).filter(Vehicle.active.is_(True)).all()
    for vehicle in vehicles:
        metrics = _calculate_resource_metrics(
            db,
            resource_type=AssignmentResourceType.vehicle,
            resource_id=vehicle.vehicle_id,
            generated_at=snapshot_time,
        )
        snapshot = ResourceFeature(
            resource_type=AssignmentResourceType.vehicle,
            vehicle_id=vehicle.vehicle_id,
            avg_delay_last_10=metrics.avg_delay_last_10,
            avg_job_duration_variance=metrics.avg_job_duration_variance,
            incident_rate_last_30d=metrics.incident_rate_last_30d,
            utilization_rate_last_30d=metrics.utilization_rate_last_30d,
            fatigue_score=metrics.fatigue_score,
            reliability_score=metrics.reliability_score,
            generated_at=snapshot_time,
        )
        db.add(snapshot)
        snapshots.append(snapshot)

    return snapshots


@dataclass
class _ResourceMetrics:
    avg_delay_last_10: Decimal
    avg_job_duration_variance: Decimal
    incident_rate_last_30d: Decimal
    utilization_rate_last_30d: Decimal
    fatigue_score: Decimal
    reliability_score: Decimal


def _calculate_resource_metrics(
    db: Session,
    *,
    resource_type: AssignmentResourceType,
    resource_id: str,
    generated_at: datetime,
    max_daily_hours: Decimal | None = None,
) -> _ResourceMetrics:
    cutoff = generated_at - timedelta(days=30)

    assignment_filter = _build_resource_filter(resource_type, resource_id)

    assignments_last_30_days = (
        db.query(Assignment)
        .filter(*assignment_filter, Assignment.planned_end >= cutoff)
        .all()
    )
    assignment_count = len(assignments_last_30_days)

    timings = (
        db.query(ActualTiming)
        .join(Assignment, Assignment.assignment_id == ActualTiming.assignment_id)
        .filter(
            *assignment_filter,
            ActualTiming.planned_end.is_not(None),
            ActualTiming.actual_end.is_not(None),
        )
        .order_by(ActualTiming.created_at.desc())
        .limit(10)
        .all()
    )

    delay_values: list[Decimal] = []
    variance_values: list[Decimal] = []
    for timing in timings:
        if timing.delay_minutes is not None:
            delay_values.append(Decimal(timing.delay_minutes))
        else:
            delay_values.append(
                Decimal(
                    int(
                        (timing.actual_end - timing.planned_end).total_seconds() // 60
                    )
                )
            )

        if timing.planned_start is not None and timing.actual_start is not None:
            planned_minutes = (timing.planned_end - timing.planned_start).total_seconds() / 60
            actual_minutes = (timing.actual_end - timing.actual_start).total_seconds() / 60
            variance_values.append(Decimal(abs(actual_minutes - planned_minutes)))

    avg_delay = _avg_decimal(delay_values, places="0.01")
    avg_variance = _avg_decimal(variance_values, places="0.01")

    incidents_last_30_days = (
        db.query(Incident)
        .join(Assignment, Assignment.assignment_id == Incident.assignment_id)
        .filter(*assignment_filter, Incident.reported_at >= cutoff)
        .count()
    )
    incident_rate = Decimal("0")
    if assignment_count > 0:
        incident_rate = _quantize(
            Decimal(incidents_last_30_days) / Decimal(assignment_count),
            places="0.0001",
        )

    utilization = _utilization_ratio(assignments_last_30_days, cutoff, generated_at)
    fatigue = _fatigue_score(
        utilization_rate=utilization,
        max_daily_hours=max_daily_hours,
    )
    reliability = _reliability_score(
        avg_delay=avg_delay,
        incident_rate=incident_rate,
        fatigue_score=fatigue,
        has_history=assignment_count > 0 or len(delay_values) > 0,
    )

    return _ResourceMetrics(
        avg_delay_last_10=avg_delay,
        avg_job_duration_variance=avg_variance,
        incident_rate_last_30d=incident_rate,
        utilization_rate_last_30d=utilization,
        fatigue_score=fatigue,
        reliability_score=reliability,
    )


def _build_resource_filter(
    resource_type: AssignmentResourceType, resource_id: str
) -> list:
    if resource_type == AssignmentResourceType.person:
        return [Assignment.resource_type == resource_type, Assignment.person_id == resource_id]
    if resource_type == AssignmentResourceType.equipment:
        return [
            Assignment.resource_type == resource_type,
            Assignment.equipment_id == resource_id,
        ]
    return [Assignment.resource_type == resource_type, Assignment.vehicle_id == resource_id]


def _quantity_to_int(value: Decimal | None) -> int:
    if value is None:
        return 0
    return int(max(ceil(float(value)), 0))


def _attendee_bucket(attendee_count: int | None) -> str:
    if attendee_count is None:
        return "unknown"
    if attendee_count <= 50:
        return "small"
    if attendee_count <= 200:
        return "medium"
    if attendee_count <= 1000:
        return "large"
    return "mega"


def _season_from_month(month: int) -> str:
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"


def _avg_decimal(values: list[Decimal], *, places: str) -> Decimal:
    if not values:
        return _quantize(Decimal("0"), places=places)
    return _quantize(sum(values) / Decimal(len(values)), places=places)


def _quantize(value: Decimal, *, places: str) -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def _utilization_ratio(
    assignments: list[Assignment], cutoff: datetime, generated_at: datetime
) -> Decimal:
    total_minutes = Decimal("0")
    for assignment in assignments:
        start = max(assignment.planned_start, cutoff)
        end = min(assignment.planned_end, generated_at)
        if end > start:
            total_minutes += Decimal((end - start).total_seconds() / 60)

    window_minutes = Decimal(30 * 24 * 60)
    if window_minutes <= 0:
        return Decimal("0.0000")
    ratio = total_minutes / window_minutes
    ratio = max(Decimal("0"), min(ratio, Decimal("1")))
    return _quantize(ratio, places="0.0001")


def _fatigue_score(
    *, utilization_rate: Decimal, max_daily_hours: Decimal | None
) -> Decimal:
    if max_daily_hours is not None and max_daily_hours > 0:
        normalized_hours = Decimal("8") / max_daily_hours
        fatigue = utilization_rate * normalized_hours
    else:
        fatigue = utilization_rate
    fatigue = max(Decimal("0"), min(fatigue, Decimal("1")))
    return _quantize(fatigue, places="0.0001")


def _reliability_score(
    *,
    avg_delay: Decimal,
    incident_rate: Decimal,
    fatigue_score: Decimal,
    has_history: bool,
) -> Decimal:
    if not has_history:
        return Decimal("0.8500")

    delay_penalty = min(avg_delay / Decimal("120"), Decimal("1")) * Decimal("0.4")
    incident_penalty = min(incident_rate, Decimal("1")) * Decimal("0.4")
    fatigue_penalty = min(fatigue_score, Decimal("1")) * Decimal("0.2")

    reliability = Decimal("1") - (delay_penalty + incident_penalty + fatigue_penalty)
    reliability = max(Decimal("0"), min(reliability, Decimal("1")))
    return _quantize(reliability, places="0.0001")
