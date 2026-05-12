from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
import pickle
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.ai import (
    EventFeature,
    ModelRegistry,
    ModelStatus,
    PlannerRecommendation,
    PlannerRecommendationAssignment,
    PlannerRun,
    PlannerRunStatus,
    PredictionType,
)
from app.models.core import (
    Assignment,
    AssignmentResourceType,
    AssignmentStatus,
    Equipment,
    EquipmentAvailability,
    Event,
    EventStatus,
    Location,
    PeopleAvailability,
    ResourceStatus,
    ResourcePerson,
    TransportLeg,
    Vehicle,
    VehicleAvailability,
)
from app.models.ops import (
    ActualTiming,
    EventExecutionLog,
    OpsLogType,
    ResourceCheckpoint,
)
from app.schemas.planner import (
    AssignmentCandidateOption,
    AssignmentSlot,
    MetricExplanation,
    GapResolutionPreviewResponse,
    GapResolutionGuidance,
    GapResolutionOption,
    GeneratedPlanAssignment,
    GeneratePlanResponse,
    PlanBusinessExplanation,
    PlanCandidateEvaluation,
    PlanMetricDelta,
    PlanMetricComparison,
    PlanMetrics,
    PlanStageBreakdown,
    ResourceImpactItem,
    RequirementGapSummary,
    RecommendBestPlanResponse,
    ResolvePlanGapsRequest,
    ResolvePlanGapsResponse,
    ReplanResponse,
    SuggestedRescheduleWindow,
)
from app.services.ortools_service import (
    PlannerCandidate,
    PlannerAssignment,
    PlannerInput,
    PlannerRequirement,
    PlannerPolicy,
    PlannerPolicyError,
    PlannerResult,
    PlannerService,
    PlannerTimeoutError,
)
from app.services.planner_input_builder import PlannerInputError, load_planner_input
from app.services.ml_feature_service import FeatureEngineeringError, generate_feature_snapshots
from app.services.datetime_service import to_utc
from app.services.observability_service import emit_event
from app.services.runtime_notification_service import enqueue_runtime_notification


class PlanGenerationError(ValueError):
    pass


@dataclass(frozen=True)
class ConsumedAssignment:
    assignment_id: str
    requirement_id: str
    resource_type: str
    resource_id: str
    estimated_cost: Decimal


@dataclass(frozen=True)
class _MetricEventFeature:
    feature_attendee_count: int | None
    feature_setup_complexity_score: int | None
    feature_access_difficulty: int | None
    feature_parking_difficulty: int | None


_PRIORITY_LOCK_EVENT_STATUSES = {"planned", "confirmed", "in_progress"}
_PRIORITY_ACCEPTED_STATUSES = {"confirmed", "in_progress"}
_PRIORITY_LOCK_ASSIGNMENT_STATUSES = {"proposed", "planned", "confirmed", "active"}


def generate_plan(
    db: Session,
    *,
    event_id: str,
    initiated_by: str | None = None,
    initiated_by_user_id: str | None = None,
    trigger_reason: str = "manual",
    commit_to_assignments: bool = True,
    solver_timeout_seconds: float = 10.0,
    fallback_enabled: bool = True,
    preserve_consumed_resources: bool = False,
    expected_event_updated_at: datetime | None = None,
) -> GeneratePlanResponse:
    event = _get_event_for_update(db, event_id)
    if event is None:
        raise PlannerInputError("Event not found")
    _validate_expected_event_version(event, expected_event_updated_at)

    original_model = load_planner_input(db, event_id)
    model = original_model
    consumed_assignments: list[ConsumedAssignment] = []
    if preserve_consumed_resources:
        consumed_assignments = _collect_consumed_assignments(db, event_id=event_id)
        model = _apply_consumed_assignments_to_input(
            planner_input=original_model,
            consumed_assignments=consumed_assignments,
        )
    planner_run = PlannerRun(
        objective_version="phase-4-cp-04-v1",
        initiated_by=initiated_by,
        initiated_by_user_id=initiated_by_user_id,
        trigger_reason=trigger_reason,
        input_snapshot={
            "planner_input": _jsonable(model),
            "policy": {
                "timeout_seconds": solver_timeout_seconds,
                "fallback_enabled": fallback_enabled,
                "preserve_consumed_resources": preserve_consumed_resources,
            },
            "consumed_assignments": _jsonable([asdict(item) for item in consumed_assignments]),
        },
    )
    db.add(planner_run)
    db.flush()

    try:
        policy = PlannerPolicy(
            timeout_seconds=solver_timeout_seconds,
            fallback_enabled=fallback_enabled,
        )
        result = PlannerService(policy=policy).solve(model)
        if consumed_assignments:
            result = _merge_consumed_with_planner_result(
                planner_result=result,
                original_input=original_model,
                consumed_assignments=consumed_assignments,
            )
        requirement_by_id = {
            requirement.requirement_id: requirement
            for requirement in original_model.requirements
        }
        recommendation = _create_recommendation(
            db=db,
            event=event,
            planner_run=planner_run,
            requirements=requirement_by_id,
            assignments=result.assignments,
            total_cost=result.estimated_cost,
            selected=commit_to_assignments,
        )

        assignment_ids: list[str] = []
        transport_leg_ids: list[str] = []
        if commit_to_assignments:
            preserved_vehicle_ids: set[str] = set()
            if preserve_consumed_resources:
                preserved_vehicle_ids = _consumed_transport_vehicle_ids(
                    db,
                    event_id=event.event_id,
                )
            assignment_ids = _commit_assignments(
                db=db,
                event=event,
                planner_run=planner_run,
                requirements=requirement_by_id,
                assignments=result.assignments,
                consumed_assignments=consumed_assignments,
            )
            transport_leg_ids = _create_transport_legs(
                db=db,
                event=event,
                planner_run=planner_run,
                assignments=result.assignments,
                requirements=requirement_by_id,
                preserve_existing_legs=preserve_consumed_resources,
                preserve_vehicle_ids=preserved_vehicle_ids,
            )
            if _is_fully_assigned(result.assignments):
                event.status = EventStatus.planned

        planner_run.finished_at = datetime.now(UTC)
        planner_run.run_status = PlannerRunStatus.completed
        planner_run.total_cost = _money(result.estimated_cost)
        planner_run.notes = _run_notes(result.assignments)
        db.commit()
        db.refresh(recommendation)
        emit_event(
            "planner.generate.completed",
            event_id=event_id,
            planner_run_id=planner_run.planner_run_id,
            recommendation_id=recommendation.recommendation_id,
            fully_assigned=_is_fully_assigned(result.assignments),
            preserve_consumed_resources=preserve_consumed_resources,
        )

        return GeneratePlanResponse(
            event_id=event_id,
            planner_run_id=planner_run.planner_run_id,
            recommendation_id=recommendation.recommendation_id,
            plan_id=result.plan_id,
            solver=result.solver,
            solver_duration_ms=result.duration_ms,
            fallback_reason=result.fallback_reason,
            fallback_enabled=fallback_enabled,
            solver_timeout_seconds=solver_timeout_seconds,
            is_fully_assigned=_is_fully_assigned(result.assignments),
            assignments=[
                _response_assignment(assignment, requirement_by_id)
                for assignment in result.assignments
            ],
            assignment_ids=assignment_ids,
            transport_leg_ids=transport_leg_ids,
            estimated_cost=_money(result.estimated_cost),
            metrics=_plan_metrics(
                event=event,
                event_feature=_metric_feature_for_event(event),
                result=result,
                planner_input=original_model,
            ),
            stage_breakdown=_plan_stage_breakdown(
                event=event,
                event_feature=_metric_feature_for_event(event),
                result=result,
                planner_input=original_model,
                total_duration_minutes=None,
            ),
            assignment_slots=_assignment_slots(
                db=db,
                event=event,
                result=result,
                planner_input=original_model,
            ),
            gap_resolution=_build_gap_resolution_guidance(
                db=db,
                event=event,
                event_id=event.event_id,
                assignments=result.assignments,
                requirements=requirement_by_id,
            ),
        )
    except (PlannerPolicyError, PlannerTimeoutError) as exc:
        planner_run.finished_at = datetime.now(UTC)
        planner_run.run_status = PlannerRunStatus.failed
        planner_run.notes = str(exc)
        db.commit()
        raise PlanGenerationError(str(exc)) from exc
    except Exception as exc:
        planner_run.finished_at = datetime.now(UTC)
        planner_run.run_status = PlannerRunStatus.failed
        planner_run.notes = str(exc)
        db.commit()
        raise PlanGenerationError(str(exc)) from exc


def replan_event(
    db: Session,
    *,
    event_id: str,
    incident_id: str | None = None,
    incident_summary: str | None = None,
    operator_actions: list[dict[str, Any]] | None = None,
    initiated_by: str | None = None,
    initiated_by_user_id: str | None = None,
    commit_to_assignments: bool = True,
    solver_timeout_seconds: float = 10.0,
    fallback_enabled: bool = True,
    preserve_consumed_resources: bool = True,
    expected_event_updated_at: datetime | None = None,
) -> ReplanResponse:
    baseline = _latest_recommendation_for_event(db, event_id)

    generated = generate_plan(
        db,
        event_id=event_id,
        initiated_by=initiated_by,
        initiated_by_user_id=initiated_by_user_id,
        trigger_reason="incident",
        commit_to_assignments=commit_to_assignments,
        solver_timeout_seconds=solver_timeout_seconds,
        fallback_enabled=fallback_enabled,
        preserve_consumed_resources=preserve_consumed_resources,
        expected_event_updated_at=expected_event_updated_at,
    )

    planner_run = db.get(PlannerRun, generated.planner_run_id)
    if planner_run is None:
        raise PlanGenerationError("Planner run not found after replanning.")

    new_recommendation = db.get(PlannerRecommendation, generated.recommendation_id)
    if new_recommendation is None:
        raise PlanGenerationError("Recommendation not found after replanning.")

    comparison = _compare_recommendations(
        previous=baseline,
        current=new_recommendation,
    )
    operator_actions = operator_actions or []
    comparison = _apply_operator_actions_to_comparison(
        db=db,
        event_id=event_id,
        comparison=comparison,
        operator_actions=operator_actions,
    )
    if commit_to_assignments and operator_actions:
        _commit_operator_action_assignments(
            db=db,
            event_id=event_id,
            planner_run_id=generated.planner_run_id,
            operator_actions=operator_actions,
        )
    enqueue_runtime_notification(
        event_id=event_id,
        notification_type="replan_completed",
        payload={
            "planner_run_id": generated.planner_run_id,
            "recommendation_id": generated.recommendation_id,
            "incident_id": incident_id,
            "is_improved": comparison.is_improved,
            "cost_delta": str(comparison.cost_delta)
            if comparison.cost_delta is not None
            else None,
            "duration_delta_minutes": comparison.duration_delta_minutes,
            "risk_delta": str(comparison.risk_delta)
            if comparison.risk_delta is not None
            else None,
            "operator_actions": operator_actions,
        },
    )
    emit_event(
        "planner.replan.completed",
        event_id=event_id,
        incident_id=incident_id,
        planner_run_id=generated.planner_run_id,
        recommendation_id=generated.recommendation_id,
        preserve_consumed_resources=preserve_consumed_resources,
    )

    return ReplanResponse(
        event_id=event_id,
        planner_run_id=generated.planner_run_id,
        planner_run_trigger_reason=planner_run.trigger_reason or "incident",
        recommendation_id=generated.recommendation_id,
        baseline_recommendation_id=(
            baseline.recommendation_id if baseline is not None else None
        ),
        incident_id=incident_id,
        incident_summary=incident_summary,
        operator_actions=operator_actions,
        comparison=comparison,
        generated_plan=generated,
    )


def resolve_plan_gaps(
    db: Session,
    *,
    event_id: str,
    payload: ResolvePlanGapsRequest,
    initiated_by_user_id: str | None = None,
    initiated_by_username: str | None = None,
) -> ResolvePlanGapsResponse:
    event = _get_event_for_update(db, event_id)
    if event is None:
        raise PlannerInputError("Event not found")
    _validate_expected_event_version(event, payload.expected_event_updated_at)

    created_people_ids: list[str] = []
    created_equipment_ids: list[str] = []
    created_vehicle_ids: list[str] = []
    updated_start: datetime | None = None
    updated_end: datetime | None = None

    if payload.strategy == "augment_resources":
        for person_input in payload.add_people:
            person = ResourcePerson(
                full_name=person_input.full_name,
                role=person_input.role,
                home_base_location_id=person_input.home_base_location_id
                or event.location_id,
                cost_per_hour=person_input.cost_per_hour,
                reliability_notes=person_input.reliability_notes,
                availability_status=ResourceStatus.available,
                active=True,
            )
            db.add(person)
            db.flush()
            created_people_ids.append(person.person_id)
            db.add(
                PeopleAvailability(
                    person_id=person.person_id,
                    available_from=person_input.available_from or event.planned_start,
                    available_to=person_input.available_to or event.planned_end,
                    is_available=True,
                    source="gap_resolution",
                    notes=f"Gap resolution for event {event_id}",
                )
            )

        for equipment_input in payload.add_equipment:
            equipment = Equipment(
                equipment_type_id=equipment_input.equipment_type_id,
                asset_tag=equipment_input.asset_tag,
                warehouse_location_id=equipment_input.warehouse_location_id
                or event.location_id,
                hourly_cost_estimate=equipment_input.hourly_cost_estimate,
                transport_requirements=equipment_input.transport_requirements,
                status=ResourceStatus.available,
                active=True,
            )
            db.add(equipment)
            db.flush()
            created_equipment_ids.append(equipment.equipment_id)
            db.add(
                EquipmentAvailability(
                    equipment_id=equipment.equipment_id,
                    available_from=equipment_input.available_from or event.planned_start,
                    available_to=equipment_input.available_to or event.planned_end,
                    is_available=True,
                    source="gap_resolution",
                    notes=f"Gap resolution for event {event_id}",
                )
            )

        for vehicle_input in payload.add_vehicles:
            vehicle = Vehicle(
                vehicle_name=vehicle_input.vehicle_name,
                vehicle_type=vehicle_input.vehicle_type,
                home_location_id=vehicle_input.home_location_id or event.location_id,
                registration_number=vehicle_input.registration_number,
                cost_per_km=vehicle_input.cost_per_km,
                cost_per_hour=vehicle_input.cost_per_hour,
                status=ResourceStatus.available,
                active=True,
            )
            db.add(vehicle)
            db.flush()
            created_vehicle_ids.append(vehicle.vehicle_id)
            db.add(
                VehicleAvailability(
                    vehicle_id=vehicle.vehicle_id,
                    available_from=vehicle_input.available_from or event.planned_start,
                    available_to=vehicle_input.available_to or event.planned_end,
                    is_available=True,
                    source="gap_resolution",
                    notes=f"Gap resolution for event {event_id}",
                )
            )

    else:
        event.planned_start = to_utc(payload.new_planned_start) or event.planned_start
        event.planned_end = to_utc(payload.new_planned_end) or event.planned_end
        if event.planned_end <= event.planned_start:
            raise PlanGenerationError("new_planned_end must be after new_planned_start.")
        updated_start = event.planned_start
        updated_end = event.planned_end
        db.add(event)

    db.flush()
    db.commit()
    db.refresh(event)

    generated = generate_plan(
        db,
        event_id=event_id,
        initiated_by=payload.initiated_by or initiated_by_username,
        initiated_by_user_id=initiated_by_user_id,
        trigger_reason="gap_resolution",
        commit_to_assignments=payload.commit_to_assignments,
        solver_timeout_seconds=payload.solver_timeout_seconds,
        fallback_enabled=payload.fallback_enabled,
        preserve_consumed_resources=True,
    )
    emit_event(
        "planner.gap_resolution.completed",
        event_id=event_id,
        strategy=payload.strategy,
        created_people=len(created_people_ids),
        created_equipment=len(created_equipment_ids),
        created_vehicles=len(created_vehicle_ids),
        updated_event_window=bool(updated_start and updated_end),
        planner_run_id=generated.planner_run_id,
    )
    if payload.strategy == "augment_resources":
        summary = (
            "Dodano nowe zasoby i dostepnosc, nastepnie wykonano ponowne planowanie."
        )
    else:
        summary = (
            "Przesunieto termin eventu i wykonano ponowne planowanie dla nowego okna."
        )

    return ResolvePlanGapsResponse(
        event_id=event_id,
        strategy=payload.strategy,
        created_people_ids=created_people_ids,
        created_equipment_ids=created_equipment_ids,
        created_vehicle_ids=created_vehicle_ids,
        updated_event_window_start=updated_start,
        updated_event_window_end=updated_end,
        generated_plan=generated,
        decision_summary=summary,
    )


def build_gap_resolution_preview(
    db: Session,
    *,
    event_id: str,
    initiated_by: str | None = None,
    initiated_by_user_id: str | None = None,
    solver_timeout_seconds: float = 10.0,
    fallback_enabled: bool = True,
) -> GapResolutionPreviewResponse:
    generated = generate_plan(
        db,
        event_id=event_id,
        initiated_by=initiated_by,
        initiated_by_user_id=initiated_by_user_id,
        trigger_reason="gap_preview",
        commit_to_assignments=False,
        solver_timeout_seconds=solver_timeout_seconds,
        fallback_enabled=fallback_enabled,
        preserve_consumed_resources=True,
    )
    return GapResolutionPreviewResponse(
        event_id=event_id,
        preview_generated_at=datetime.now(UTC),
        generated_plan=generated,
    )


def recommend_best_plan_with_ml(
    db: Session,
    *,
    event_id: str,
    initiated_by: str | None = None,
    initiated_by_user_id: str | None = None,
    commit_to_assignments: bool = False,
    solver_timeout_seconds: float = 10.0,
    fallback_enabled: bool = True,
    duration_model_id: str | None = None,
    plan_evaluator_model_id: str | None = None,
    assignment_overrides: list[dict[str, Any]] | None = None,
) -> RecommendBestPlanResponse:
    event = db.get(Event, event_id)
    if event is None:
        raise PlannerInputError("Event not found")

    event_feature = db.get(EventFeature, event_id)
    if event_feature is None:
        try:
            generated_features = generate_feature_snapshots(
                db,
                event_id=event_id,
                include_event_feature=True,
                include_resource_features=True,
            )
        except FeatureEngineeringError as exc:
            raise PlanGenerationError(str(exc)) from exc
        event_feature = generated_features.event_feature
    if event_feature is None:
        raise PlanGenerationError("Event feature snapshot could not be generated.")

    planner_input = load_planner_input(db, event_id)
    if not planner_input.requirements:
        raise PlanGenerationError("Planner input has no requirements to optimize.")

    try:
        duration_artifact = _resolve_model_artifact(
            db=db,
            prediction_type=PredictionType.duration_estimate,
            preferred_model_id=duration_model_id,
        )
    except PlanGenerationError:
        if not fallback_enabled:
            raise
        planned_minutes = max((event.planned_end - event.planned_start).total_seconds() / 60, 1)
        duration_artifact = {
            "kind": "mean_regressor",
            "mean_value": planned_minutes,
            "source": "runtime_fallback_missing_duration_artifact",
        }
    plan_evaluator_artifact = _resolve_plan_evaluator_artifact(
        db=db,
        preferred_model_id=plan_evaluator_model_id,
    )

    settings = get_settings()
    planner_run = PlannerRun(
        objective_version="phase-7-cp-07-ml-plan-proposal-v1",
        initiated_by=initiated_by,
        initiated_by_user_id=initiated_by_user_id,
        trigger_reason="ml_recommendation",
        input_snapshot={
            "event_id": event_id,
            "policy": {
                "timeout_seconds": solver_timeout_seconds,
                "fallback_enabled": fallback_enabled,
            },
            "profiles": [profile["name"] for profile in _proposal_profiles()],
            "guardrails": {
                "confidence_min": settings.ml_plan_guardrail_confidence_min,
                "ood_max": settings.ml_plan_guardrail_ood_max,
                "high_risk_max": settings.ml_plan_guardrail_high_risk_max,
            },
        },
    )
    db.add(planner_run)
    db.flush()

    policy = PlannerPolicy(
        timeout_seconds=solver_timeout_seconds,
        fallback_enabled=fallback_enabled,
    )
    base_duration_minutes = _predict_duration_minutes(duration_artifact, event_feature)
    candidate_results: list[dict[str, Any]] = []
    requirement_by_id = {
        requirement.requirement_id: requirement for requirement in planner_input.requirements
    }

    for profile in _proposal_profiles():
        profiled_input = _apply_profile_to_planner_input(
            planner_input=planner_input,
            score_weight=profile["score_weight"],
            cost_weight=profile["cost_weight"],
            reliability_bias=profile["reliability_bias"],
            risk_bias=profile["risk_bias"],
        )
        solved = PlannerService(policy=policy).solve(profiled_input)
        total_required = sum(max(requirement.quantity, 0) for requirement in profiled_input.requirements)
        unassigned_count = sum(item.unassigned_count for item in solved.assignments)
        coverage_ratio = Decimal("1.0000")
        if total_required > 0:
            coverage_ratio = _ratio_decimal(
                Decimal(total_required - unassigned_count),
                Decimal(total_required),
            )

        predicted_duration_minutes = _candidate_duration_minutes(
            base_duration_minutes=base_duration_minutes,
            coverage_ratio=coverage_ratio,
            estimated_cost=solved.estimated_cost,
        )
        profile_duration_multiplier = (
            Decimal("1")
            - Decimal(str(profile["reliability_bias"])) * Decimal("0.16")
            + Decimal(str(profile["risk_bias"])) * Decimal("0.08")
        )
        predicted_duration_minutes = (
            predicted_duration_minutes * max(profile_duration_multiplier, Decimal("0.80"))
        ).quantize(Decimal("0.0001"))
        predicted_duration_minutes = (
            predicted_duration_minutes
            + _max_assignment_travel_minutes(solved.assignments, profiled_input) * Decimal("0.30")
        ).quantize(Decimal("0.0001"))
        duration_breakdown = _duration_breakdown(
            event=event,
            event_feature=event_feature,
            total_duration_minutes=predicted_duration_minutes,
        )
        delay_risk = _candidate_delay_risk(
            predicted_duration_minutes=predicted_duration_minutes,
            event=event,
            coverage_ratio=coverage_ratio,
            unassigned_count=unassigned_count,
            total_required=total_required,
        )
        incident_risk = _candidate_incident_risk(
            event_feature=event_feature,
            coverage_ratio=coverage_ratio,
            unassigned_count=unassigned_count,
            risk_bias=Decimal(str(profile["risk_bias"])),
        )
        sla_breach_risk = _candidate_sla_risk(
            delay_risk=delay_risk,
            incident_risk=incident_risk,
            event=event,
            predicted_total_duration_minutes=predicted_duration_minutes,
        )
        predicted_risk = _candidate_risk(
            coverage_ratio=coverage_ratio,
            unassigned_count=unassigned_count,
            total_required=total_required,
            risk_bias=Decimal(str(profile["risk_bias"])),
        )
        confidence_score = _plan_confidence_score(
            plan_evaluator_artifact=plan_evaluator_artifact,
            coverage_ratio=coverage_ratio,
            unassigned_count=unassigned_count,
        )
        ood_score = _ood_score(event_feature)
        ml_score = _candidate_quality_score(
            event_feature=event_feature,
            coverage_ratio=coverage_ratio,
            unassigned_count=unassigned_count,
            total_required=total_required,
            estimated_cost=solved.estimated_cost,
            predicted_duration_minutes=predicted_duration_minutes,
            predicted_risk=predicted_risk,
            profile=profile,
            reliability_score=_assignment_reliability_score(solved.assignments, profiled_input),
            backup_coverage_ratio=_backup_coverage_ratio(solved.assignments, profiled_input),
            event_budget=event.budget_estimate,
            plan_evaluator_artifact=plan_evaluator_artifact,
        )
        plan_score = _plan_score(
            estimated_cost=solved.estimated_cost,
            total_duration_minutes=predicted_duration_minutes,
            delay_risk=delay_risk,
            incident_risk=incident_risk,
            sla_breach_risk=sla_breach_risk,
            coverage_ratio=coverage_ratio,
            ml_quality_score=Decimal(str(ml_score)),
            profile=profile,
        )
        guardrail_applied, guardrail_reason = _apply_guardrails(
            candidate_name=str(profile["name"]),
            confidence_score=confidence_score,
            ood_score=ood_score,
            delay_risk=delay_risk,
            incident_risk=incident_risk,
            sla_breach_risk=sla_breach_risk,
            settings=settings,
        )
        if guardrail_applied:
            plan_score = max(plan_score - Decimal("20.0000"), Decimal("0.0000"))
        selection_explanation = _selection_explanation(
            candidate_name=str(profile["name"]),
            plan_score=plan_score,
            estimated_cost=solved.estimated_cost,
            total_duration_minutes=predicted_duration_minutes,
            delay_risk=delay_risk,
            incident_risk=incident_risk,
            sla_breach_risk=sla_breach_risk,
            coverage_ratio=coverage_ratio,
            guardrail_applied=guardrail_applied,
            guardrail_reason=guardrail_reason,
        )
        candidate_results.append(
            {
                "profile": profile,
                "planner_result": solved,
                "coverage_ratio": coverage_ratio,
                "unassigned_count": unassigned_count,
                "predicted_duration_minutes": predicted_duration_minutes,
                "predicted_transport_duration_minutes": duration_breakdown["transport_duration_minutes"],
                "predicted_setup_duration_minutes": duration_breakdown["setup_duration_minutes"],
                "predicted_teardown_duration_minutes": duration_breakdown["teardown_duration_minutes"],
                "predicted_delay_risk": delay_risk,
                "predicted_incident_risk": incident_risk,
                "predicted_sla_breach_risk": sla_breach_risk,
                "predicted_risk": predicted_risk,
                "confidence_score": confidence_score,
                "ood_score": ood_score,
                "ml_score": ml_score,
                "plan_score": plan_score,
                "guardrail_applied": guardrail_applied,
                "guardrail_reason": guardrail_reason,
                "selection_explanation": selection_explanation,
                "profiled_input": profiled_input,
                "reliability_score": _assignment_reliability_score(solved.assignments, profiled_input),
                "backup_coverage_ratio": _backup_coverage_ratio(solved.assignments, profiled_input),
            }
        )

    if not candidate_results:
        raise PlanGenerationError("No candidate plans generated for ML recommendation.")

    candidate_results.sort(key=lambda item: item["plan_score"], reverse=True)
    selected = candidate_results[0]
    baseline_result = PlannerService(policy=policy).solve(planner_input)
    baseline_metrics = _plan_metrics(
        event=event,
        event_feature=event_feature,
        result=baseline_result,
        planner_input=planner_input,
    )
    selected_result: PlannerResult = selected["planner_result"]
    if assignment_overrides:
        selected_result = _apply_assignment_overrides(
            db=db,
            event=event,
            result=selected_result,
            overrides=assignment_overrides,
        )
    recommendation = _create_recommendation(
        db=db,
        event=event,
        planner_run=planner_run,
        requirements=requirement_by_id,
        assignments=selected_result.assignments,
        total_cost=selected_result.estimated_cost,
        selected=commit_to_assignments,
    )

    assignment_ids: list[str] = []
    transport_leg_ids: list[str] = []
    if commit_to_assignments:
        assignment_ids = _commit_assignments(
            db=db,
            event=event,
            planner_run=planner_run,
            requirements=requirement_by_id,
            assignments=selected_result.assignments,
        )
        transport_leg_ids = _create_transport_legs(
            db=db,
            event=event,
            planner_run=planner_run,
            assignments=selected_result.assignments,
            requirements=requirement_by_id,
        )
        if _is_fully_assigned(selected_result.assignments):
            event.status = EventStatus.planned

    planner_run.finished_at = datetime.now(UTC)
    planner_run.run_status = PlannerRunStatus.completed
    planner_run.total_cost = _money(selected_result.estimated_cost)
    planner_run.total_risk_score = selected["predicted_risk"].quantize(Decimal("0.0001"))
    planner_run.notes = (
        f"Selected profile={selected['profile']['name']} plan_score={selected['plan_score']}; "
        f"candidates={len(candidate_results)}"
    )
    planner_run.input_snapshot = {
        **(planner_run.input_snapshot or {}),
        "selected_candidate": {
            "name": selected["profile"]["name"],
            "plan_score": str(selected["plan_score"]),
            "confidence_score": str(selected["confidence_score"]),
            "ood_score": str(selected["ood_score"]),
            "predictions": {
                "transport_duration_minutes": str(selected["predicted_transport_duration_minutes"]),
                "setup_duration_minutes": str(selected["predicted_setup_duration_minutes"]),
                "teardown_duration_minutes": str(selected["predicted_teardown_duration_minutes"]),
                "total_duration_minutes": str(selected["predicted_duration_minutes"]),
                "cost_estimate": str(_money(selected_result.estimated_cost)),
                "delay_risk": str(selected["predicted_delay_risk"]),
                "incident_risk": str(selected["predicted_incident_risk"]),
                "sla_breach_risk": str(selected["predicted_sla_breach_risk"]),
            },
            "guardrail_applied": selected["guardrail_applied"],
            "guardrail_reason": selected["guardrail_reason"],
            "selection_explanation": selected["selection_explanation"],
        }
    }
    db.commit()
    db.refresh(recommendation)

    selected_plan = GeneratePlanResponse(
        event_id=event_id,
        planner_run_id=planner_run.planner_run_id,
        recommendation_id=recommendation.recommendation_id,
        plan_id=selected_result.plan_id,
        solver=selected_result.solver,
        solver_duration_ms=selected_result.duration_ms,
        fallback_reason=selected_result.fallback_reason,
        fallback_enabled=fallback_enabled,
        solver_timeout_seconds=solver_timeout_seconds,
        is_fully_assigned=_is_fully_assigned(selected_result.assignments),
        assignments=[
            _response_assignment(assignment, requirement_by_id)
            for assignment in selected_result.assignments
            ],
        assignment_ids=assignment_ids,
        transport_leg_ids=transport_leg_ids,
        estimated_cost=_money(selected_result.estimated_cost),
        metrics=_selected_plan_metrics(event=event, selected=selected, result=selected_result),
        stage_breakdown=_plan_stage_breakdown(
            event=event,
            event_feature=event_feature,
            result=selected_result,
            planner_input=selected["profiled_input"],
            total_duration_minutes=selected["predicted_duration_minutes"],
        ),
        assignment_slots=_assignment_slots(
            db=db,
            event=event,
            result=selected_result,
            planner_input=selected["profiled_input"],
        ),
        gap_resolution=_build_gap_resolution_guidance(
            db=db,
            event=event,
            event_id=event.event_id,
            assignments=selected_result.assignments,
            requirements=requirement_by_id,
        ),
    )

    return RecommendBestPlanResponse(
        event_id=event_id,
        planner_run_id=planner_run.planner_run_id,
        recommendation_id=recommendation.recommendation_id,
        selected_candidate_name=str(selected["profile"]["name"]),
        selected_plan_score=selected["plan_score"].quantize(Decimal("0.0001")),
        selected_explanation=str(selected["selection_explanation"]),
        selected_plan=selected_plan,
        baseline_metrics=baseline_metrics,
        optimized_metrics=selected_plan.metrics,
        metric_deltas=_metric_delta(baseline_metrics, selected_plan.metrics),
        business_explanation=_build_business_explanation(
            db=db,
            event=event,
            baseline_result=baseline_result,
            optimized_result=selected_result,
            baseline_metrics=baseline_metrics,
            optimized_metrics=selected_plan.metrics,
            metric_deltas=_metric_delta(baseline_metrics, selected_plan.metrics),
            optimized_input=selected["profiled_input"],
            selected_explanation=str(selected["selection_explanation"]),
        ),
        candidates=[
            PlanCandidateEvaluation(
                candidate_name=str(item["profile"]["name"]),
                solver=item["planner_result"].solver,
                estimated_cost=_money(item["planner_result"].estimated_cost),
                predicted_transport_duration_minutes=item["predicted_transport_duration_minutes"].quantize(Decimal("0.0001")),
                predicted_setup_duration_minutes=item["predicted_setup_duration_minutes"].quantize(Decimal("0.0001")),
                predicted_teardown_duration_minutes=item["predicted_teardown_duration_minutes"].quantize(Decimal("0.0001")),
                estimated_duration_minutes=item["predicted_duration_minutes"].quantize(Decimal("0.0001")),
                predicted_delay_risk=item["predicted_delay_risk"].quantize(Decimal("0.0001")),
                predicted_incident_risk=item["predicted_incident_risk"].quantize(Decimal("0.0001")),
                predicted_sla_breach_risk=item["predicted_sla_breach_risk"].quantize(Decimal("0.0001")),
                coverage_ratio=item["coverage_ratio"].quantize(Decimal("0.0001")),
                unassigned_count=int(item["unassigned_count"]),
                confidence_score=item["confidence_score"].quantize(Decimal("0.0001")),
                ood_score=item["ood_score"].quantize(Decimal("0.0001")),
                guardrail_applied=bool(item["guardrail_applied"]),
                guardrail_reason=item["guardrail_reason"],
                plan_score=item["plan_score"].quantize(Decimal("0.0001")),
                selection_explanation=str(item["selection_explanation"]),
                profile_weights={
                    "score_weight": Decimal(str(item["profile"]["score_weight"])),
                    "cost_weight": Decimal(str(item["profile"]["cost_weight"])),
                    "reliability_bias": Decimal(str(item["profile"]["reliability_bias"])),
                    "risk_bias": Decimal(str(item["profile"]["risk_bias"])),
                },
            )
            for item in candidate_results
        ],
    )


def _create_recommendation(
    *,
    db: Session,
    event: Event,
    planner_run: PlannerRun,
    requirements: dict[str, PlannerRequirement],
    assignments: list[PlannerAssignment],
    total_cost: Decimal,
    selected: bool,
) -> PlannerRecommendation:
    recommendation = PlannerRecommendation(
        planner_run_id=planner_run.planner_run_id,
        event_id=event.event_id,
        expected_cost=_money(total_cost),
        expected_duration_minutes=_event_duration_minutes(event),
        expected_risk=_risk_from_unassigned(assignments),
        selected_for_execution=selected,
        rationale=_recommendation_rationale(assignments),
    )
    db.add(recommendation)
    db.flush()

    for assignment in assignments:
        requirement = requirements[assignment.requirement_id]
        for resource_id in assignment.resource_ids:
            db.add(
                PlannerRecommendationAssignment(
                    recommendation_id=recommendation.recommendation_id,
                    resource_type=_assignment_resource_type(requirement),
                    **_resource_fk(requirement.resource_type, resource_id),
                    assignment_role=_assignment_role(requirement),
                    planned_start=requirement.required_start,
                    planned_end=requirement.required_end,
                    risk_score=Decimal("0"),
                    cost_estimate=_money(_resource_cost_share(assignment)),
                )
            )

    return recommendation


def _apply_assignment_overrides(
    *,
    db: Session,
    event: Event,
    result: PlannerResult,
    overrides: list[dict[str, Any]],
) -> PlannerResult:
    _validate_override_resource_uniqueness(overrides)
    override_by_requirement = {
        str(item.get("requirement_id")): [
            str(resource_id)
            for resource_id in item.get("resource_ids", [])
            if str(resource_id).strip()
        ]
        for item in overrides
        if item.get("requirement_id")
    }
    resource_type_by_requirement = {
        str(item.get("requirement_id")): str(item.get("resource_type") or "")
        for item in overrides
        if item.get("requirement_id")
    }
    if not override_by_requirement:
        return result

    assignments: list[PlannerAssignment] = []
    for assignment in result.assignments:
        required_count = len(assignment.resource_ids) + assignment.unassigned_count
        resource_ids = override_by_requirement.get(
            assignment.requirement_id, assignment.resource_ids
        )
        estimated_cost = _override_assignment_cost(
            db=db,
            event=event,
            resource_type=resource_type_by_requirement.get(assignment.requirement_id, ""),
            resource_ids=resource_ids,
            fallback=assignment.estimated_cost,
        )
        assignments.append(
            PlannerAssignment(
                requirement_id=assignment.requirement_id,
                resource_ids=resource_ids,
                unassigned_count=max(required_count - len(resource_ids), 0),
                estimated_cost=estimated_cost,
            )
        )
    estimated_total = sum((assignment.estimated_cost for assignment in assignments), Decimal("0"))
    return PlannerResult(
        plan_id=result.plan_id,
        solver=result.solver,
        assignments=assignments,
        estimated_cost=_money(estimated_total) if estimated_total > 0 else result.estimated_cost,
        duration_ms=result.duration_ms,
        fallback_reason=result.fallback_reason,
    )


def _validate_override_resource_uniqueness(overrides: list[dict[str, Any]]) -> None:
    seen: set[tuple[str, str]] = set()
    duplicates: list[str] = []
    for item in overrides:
        resource_type = str(item.get("resource_type") or "")
        for resource_id in item.get("resource_ids", []):
            key = (resource_type, str(resource_id))
            if key in seen:
                duplicates.append(str(resource_id))
            seen.add(key)
    if duplicates:
        raise PlanGenerationError("The same resource cannot be assigned to multiple slots in one plan.")


def _override_assignment_cost(
    *,
    db: Session,
    event: Event,
    resource_type: str,
    resource_ids: list[str],
    fallback: Decimal,
) -> Decimal:
    if not resource_ids:
        return fallback
    duration_hours = Decimal(str(max((event.planned_end - event.planned_start).total_seconds(), 0) / 3600.0))
    total = Decimal("0")
    for resource_id in resource_ids:
        if resource_type == "person":
            person = db.get(ResourcePerson, resource_id)
            if person and person.cost_per_hour is not None:
                total += person.cost_per_hour * duration_hours
                total += _override_logistics_cost(db, event, person.current_location_id or person.home_base_location_id, Decimal("1.10"))
        elif resource_type == "equipment":
            equipment = db.get(Equipment, resource_id)
            if equipment and equipment.hourly_cost_estimate is not None:
                total += equipment.hourly_cost_estimate * duration_hours
                total += _override_logistics_cost(db, event, equipment.current_location_id or equipment.warehouse_location_id, Decimal("1.50"))
        elif resource_type == "vehicle":
            vehicle = db.get(Vehicle, resource_id)
            if vehicle and vehicle.cost_per_hour is not None:
                total += vehicle.cost_per_hour * duration_hours
                total += _override_logistics_cost(db, event, vehicle.current_location_id or vehicle.home_location_id, vehicle.cost_per_km or Decimal("2.80"))
    return _money(total) if total > 0 else fallback


def _override_logistics_cost(
    db: Session,
    event: Event,
    origin_location_id: str | None,
    cost_per_km: Decimal,
) -> Decimal:
    if origin_location_id is None or event.location_id is None:
        return Decimal("0")
    origin = db.get(Location, origin_location_id)
    destination = db.get(Location, event.location_id)
    if origin is None or destination is None:
        return Decimal("0")
    distance = _distance_km(origin, destination)
    if distance is None:
        return Decimal("0")
    return _money(distance * cost_per_km * Decimal("2"))


def _commit_assignments(
    *,
    db: Session,
    event: Event,
    planner_run: PlannerRun,
    requirements: dict[str, PlannerRequirement],
    assignments: list[PlannerAssignment],
    consumed_assignments: list[ConsumedAssignment] | None = None,
) -> list[str]:
    _lock_and_validate_assignment_conflicts(
        db=db,
        event=event,
        requirements=requirements,
        assignments=assignments,
    )
    consumed_assignment_ids = {
        item.assignment_id for item in (consumed_assignments or [])
    }
    delete_query = delete(Assignment).where(
        Assignment.event_id == event.event_id,
        Assignment.is_manual_override.is_(False),
        Assignment.status.in_([AssignmentStatus.proposed, AssignmentStatus.planned]),
    )
    if consumed_assignment_ids:
        delete_query = delete_query.where(
            Assignment.assignment_id.notin_(consumed_assignment_ids)
        )
    db.execute(delete_query)
    db.flush()

    consumed_key_set = {
        (item.requirement_id, item.resource_id) for item in (consumed_assignments or [])
    }
    assignment_ids: list[str] = list(consumed_assignment_ids)
    for assignment in assignments:
        requirement = requirements[assignment.requirement_id]
        for resource_id in assignment.resource_ids:
            if (assignment.requirement_id, resource_id) in consumed_key_set:
                continue
            core_assignment = Assignment(
                event_id=event.event_id,
                resource_type=_assignment_resource_type(requirement),
                **_resource_fk(requirement.resource_type, resource_id),
                assignment_role=_assignment_role(requirement),
                planned_start=requirement.required_start,
                planned_end=requirement.required_end,
                status=AssignmentStatus.planned,
                planner_run_id=planner_run.planner_run_id,
                is_manual_override=False,
                notes=f"Generated from requirement {requirement.requirement_id}",
            )
            db.add(core_assignment)
            db.flush()
            assignment_ids.append(core_assignment.assignment_id)

    return assignment_ids


def _lock_and_validate_assignment_conflicts(
    *,
    db: Session,
    event: Event,
    requirements: dict[str, PlannerRequirement],
    assignments: list[PlannerAssignment],
) -> None:
    proposed: list[tuple[str, str, datetime, datetime]] = []
    for item in assignments:
        requirement = requirements.get(item.requirement_id)
        if requirement is None:
            continue
        resource_type = requirement.resource_type
        for resource_id in item.resource_ids:
            proposed.append(
                (
                    resource_type,
                    resource_id,
                    requirement.required_start,
                    requirement.required_end,
                )
            )

    if not proposed:
        return

    for resource_type, resource_id, _, _ in proposed:
        if resource_type == "person":
            (
                db.query(ResourcePerson)
                .filter(ResourcePerson.person_id == resource_id)
                .with_for_update()
                .first()
            )
        elif resource_type == "equipment":
            (
                db.query(Equipment)
                .filter(Equipment.equipment_id == resource_id)
                .with_for_update()
                .first()
            )
        elif resource_type == "vehicle":
            (
                db.query(Vehicle)
                .filter(Vehicle.vehicle_id == resource_id)
                .with_for_update()
                .first()
            )

    current_status = event.status.value
    for resource_type, resource_id, start, end in proposed:
        conflict_query = (
            db.query(Assignment, Event)
            .join(Event, Event.event_id == Assignment.event_id)
            .filter(
                Assignment.event_id != event.event_id,
                Assignment.planned_start < end,
                Assignment.planned_end > start,
                Event.status.in_(_PRIORITY_LOCK_EVENT_STATUSES),
                Assignment.status.in_(_PRIORITY_LOCK_ASSIGNMENT_STATUSES),
            )
            .with_for_update()
        )
        if resource_type == "person":
            conflict_query = conflict_query.filter(Assignment.person_id == resource_id)
        elif resource_type == "equipment":
            conflict_query = conflict_query.filter(Assignment.equipment_id == resource_id)
        elif resource_type == "vehicle":
            conflict_query = conflict_query.filter(Assignment.vehicle_id == resource_id)
        else:
            continue

        conflict = conflict_query.first()
        if conflict is None:
            continue
        conflict_assignment, conflict_event = conflict
        conflict_status = conflict_event.status.value
        conflict_higher_or_equal = _other_event_has_priority_over_current(
            other_event=conflict_event,
            other_status=conflict_status,
            current_event=event,
            current_status=current_status,
        )
        if conflict_higher_or_equal:
            raise PlanGenerationError(
                "Atomic assignment lock conflict for "
                f"{resource_type}:{resource_id} with event {conflict_event.event_id} "
                f"(relation=higher_or_equal_priority, assignment_id={conflict_assignment.assignment_id})."
            )

        can_preempt = (
            not conflict_assignment.is_manual_override
            and not conflict_assignment.is_consumed_in_execution
            and conflict_assignment.status
            in {AssignmentStatus.proposed, AssignmentStatus.planned}
        )
        if not can_preempt:
            raise PlanGenerationError(
                "Atomic assignment lock conflict for "
                f"{resource_type}:{resource_id} with event {conflict_event.event_id} "
                "(relation=lower_priority_but_non_preemptable)."
            )
        db.delete(conflict_assignment)
        if resource_type == "vehicle":
            db.execute(
                delete(TransportLeg).where(
                    TransportLeg.event_id == conflict_event.event_id,
                    TransportLeg.vehicle_id == resource_id,
                    TransportLeg.notes.like("Generated by planner run%"),
                )
            )
        emit_event(
            "planner.priority_preemption",
            event_id=event.event_id,
            preempted_event_id=conflict_event.event_id,
            resource_type=resource_type,
            resource_id=resource_id,
            preempted_assignment_id=conflict_assignment.assignment_id,
        )


def _create_transport_legs(
    *,
    db: Session,
    event: Event,
    planner_run: PlannerRun,
    assignments: list[PlannerAssignment],
    requirements: dict[str, PlannerRequirement],
    preserve_existing_legs: bool = False,
    preserve_vehicle_ids: set[str] | None = None,
) -> list[str]:
    if not event.requires_transport:
        return []

    existing_leg_by_vehicle: dict[str, str] = {}
    if preserve_existing_legs:
        allowed_vehicle_ids = preserve_vehicle_ids or set()
        existing_legs = (
            db.query(TransportLeg)
            .filter(TransportLeg.event_id == event.event_id)
            .all()
        )
        for leg in existing_legs:
            if leg.vehicle_id and leg.vehicle_id in allowed_vehicle_ids:
                existing_leg_by_vehicle[leg.vehicle_id] = leg.transport_leg_id
            else:
                db.delete(leg)
        db.flush()
    else:
        db.execute(
            delete(TransportLeg).where(
                TransportLeg.event_id == event.event_id,
                TransportLeg.notes.like("Generated by planner run%"),
            )
        )
        db.flush()

    driver_id = _first_driver(db, assignments, requirements)
    leg_ids: list[str] = list(existing_leg_by_vehicle.values())
    for vehicle_id in _assigned_vehicle_ids(assignments, requirements):
        if vehicle_id in existing_leg_by_vehicle:
            continue
        vehicle = db.get(Vehicle, vehicle_id)
        if vehicle is None or (vehicle.current_location_id is None and vehicle.home_location_id is None):
            continue
        origin_location_id = vehicle.current_location_id or vehicle.home_location_id
        if origin_location_id == event.location_id:
            continue

        origin = db.get(Location, origin_location_id)
        destination = db.get(Location, event.location_id)
        if origin is None or destination is None:
            continue

        distance = _distance_km(origin, destination)
        duration_minutes = _transport_duration_minutes(distance)
        transport_leg = TransportLeg(
            event_id=event.event_id,
            vehicle_id=vehicle.vehicle_id,
            driver_person_id=driver_id,
            origin_location_id=origin.location_id,
            destination_location_id=destination.location_id,
            planned_departure=event.planned_start - timedelta(minutes=duration_minutes),
            planned_arrival=event.planned_start,
            estimated_distance_km=distance,
            estimated_duration_minutes=duration_minutes,
            notes=f"Generated by planner run {planner_run.planner_run_id}",
        )
        db.add(transport_leg)
        db.flush()
        leg_ids.append(transport_leg.transport_leg_id)

    return leg_ids


def _collect_consumed_assignments(
    db: Session,
    *,
    event_id: str,
) -> list[ConsumedAssignment]:
    consumed_ids = _consumed_assignment_ids(db, event_id=event_id)
    if not consumed_ids:
        return []

    assignments = (
        db.query(Assignment)
        .filter(
            Assignment.event_id == event_id,
            Assignment.assignment_id.in_(consumed_ids),
        )
        .all()
    )

    consumed: list[ConsumedAssignment] = []
    for assignment in assignments:
        requirement_id = _extract_requirement_id_from_role(assignment.assignment_role)
        if not requirement_id:
            continue
        resource_id = _assignment_resource_id(assignment)
        if resource_id is None:
            continue
        consumed.append(
            ConsumedAssignment(
                assignment_id=assignment.assignment_id,
                requirement_id=requirement_id,
                resource_type=assignment.resource_type.value,
                resource_id=resource_id,
                estimated_cost=_assignment_estimated_cost(db, assignment),
            )
        )
    return consumed


def _consumed_assignment_ids(db: Session, *, event_id: str) -> set[str]:
    consumed_ids: set[str] = set()
    consumed_by_flag = (
        db.query(Assignment.assignment_id)
        .filter(
            Assignment.event_id == event_id,
            Assignment.is_consumed_in_execution.is_(True),
        )
        .all()
    )
    consumed_ids.update(item[0] for item in consumed_by_flag if item[0])

    status_consumed = (
        db.query(Assignment.assignment_id)
        .filter(
            Assignment.event_id == event_id,
            Assignment.status.in_(
                [
                    AssignmentStatus.active,
                    AssignmentStatus.completed,
                    AssignmentStatus.confirmed,
                ]
            ),
        )
        .all()
    )
    consumed_ids.update(item[0] for item in status_consumed if item[0])

    checkpoint_consumed = (
        db.query(ResourceCheckpoint.assignment_id)
        .filter(
            ResourceCheckpoint.event_id == event_id,
            ResourceCheckpoint.assignment_id.isnot(None),
        )
        .all()
    )
    consumed_ids.update(item[0] for item in checkpoint_consumed if item[0])

    timing_consumed = (
        db.query(ActualTiming.assignment_id)
        .filter(
            ActualTiming.event_id == event_id,
            ActualTiming.assignment_id.isnot(None),
            ActualTiming.actual_start.isnot(None),
        )
        .all()
    )
    consumed_ids.update(item[0] for item in timing_consumed if item[0])

    log_consumed = (
        db.query(EventExecutionLog.assignment_id)
        .filter(
            EventExecutionLog.event_id == event_id,
            EventExecutionLog.assignment_id.isnot(None),
            EventExecutionLog.log_type.in_(
                [
                    OpsLogType.transport_started,
                    OpsLogType.transport_arrived,
                    OpsLogType.setup_started,
                    OpsLogType.setup_completed,
                    OpsLogType.teardown_started,
                    OpsLogType.teardown_completed,
                    OpsLogType.event_started,
                ]
            ),
        )
        .all()
    )
    consumed_ids.update(item[0] for item in log_consumed if item[0])

    return consumed_ids


def _consumed_transport_vehicle_ids(db: Session, *, event_id: str) -> set[str]:
    from_checkpoint = (
        db.query(ResourceCheckpoint.vehicle_id)
        .filter(
            ResourceCheckpoint.event_id == event_id,
            ResourceCheckpoint.vehicle_id.isnot(None),
            ResourceCheckpoint.checkpoint_type.in_(
                [
                    "transport_started",
                    "transport_arrived",
                    "loadout_started",
                    "loadout_completed",
                ]
            ),
        )
        .all()
    )
    ids: set[str] = {item[0] for item in from_checkpoint if item[0]}

    from_logs = (
        db.query(Assignment.vehicle_id)
        .join(EventExecutionLog, EventExecutionLog.assignment_id == Assignment.assignment_id)
        .filter(
            Assignment.event_id == event_id,
            Assignment.vehicle_id.isnot(None),
            EventExecutionLog.log_type.in_(
                [OpsLogType.transport_started, OpsLogType.transport_arrived]
            ),
        )
        .all()
    )
    ids.update(item[0] for item in from_logs if item[0])
    return ids


def _apply_consumed_assignments_to_input(
    *,
    planner_input: PlannerInput,
    consumed_assignments: list[ConsumedAssignment],
) -> PlannerInput:
    consumed_by_requirement: dict[str, set[str]] = {}
    for item in consumed_assignments:
        consumed_by_requirement.setdefault(item.requirement_id, set()).add(item.resource_id)

    adjusted_requirements: list[PlannerRequirement] = []
    for requirement in planner_input.requirements:
        consumed_ids = consumed_by_requirement.get(requirement.requirement_id, set())
        adjusted_quantity = max(requirement.quantity - len(consumed_ids), 0)
        adjusted_candidates = [
            candidate
            for candidate in requirement.candidates
            if candidate.resource_id not in consumed_ids
        ]
        adjusted_requirements.append(
            PlannerRequirement(
                requirement_id=requirement.requirement_id,
                resource_type=requirement.resource_type,
                quantity=adjusted_quantity,
                mandatory=requirement.mandatory,
                required_start=requirement.required_start,
                required_end=requirement.required_end,
                candidates=adjusted_candidates,
            )
        )
    return PlannerInput(requirements=adjusted_requirements)


def _merge_consumed_with_planner_result(
    *,
    planner_result: PlannerResult,
    original_input: PlannerInput,
    consumed_assignments: list[ConsumedAssignment],
) -> PlannerResult:
    requirement_map = {
        requirement.requirement_id: requirement for requirement in original_input.requirements
    }
    consumed_by_requirement: dict[str, list[ConsumedAssignment]] = {}
    for item in consumed_assignments:
        consumed_by_requirement.setdefault(item.requirement_id, []).append(item)

    merged_assignments: list[PlannerAssignment] = []
    merged_cost = Decimal("0")
    for assignment in planner_result.assignments:
        requirement = requirement_map.get(assignment.requirement_id)
        consumed_items = consumed_by_requirement.get(assignment.requirement_id, [])
        consumed_resource_ids = [item.resource_id for item in consumed_items]
        required_qty = requirement.quantity if requirement is not None else len(consumed_resource_ids)
        unique_new_ids = [
            resource_id
            for resource_id in assignment.resource_ids
            if resource_id not in consumed_resource_ids
        ]
        remaining_slots = max(required_qty - len(consumed_resource_ids), 0)
        selected_new_ids = unique_new_ids[:remaining_slots]
        merged_ids = list(dict.fromkeys(consumed_resource_ids + selected_new_ids))
        unassigned_count = max(required_qty - len(merged_ids), 0)
        consumed_cost = sum((item.estimated_cost for item in consumed_items), Decimal("0"))
        new_cost = Decimal("0")
        if assignment.resource_ids:
            per_resource_cost = assignment.estimated_cost / Decimal(len(assignment.resource_ids))
            new_cost = per_resource_cost * Decimal(len(selected_new_ids))
        merged_assignment = PlannerAssignment(
            requirement_id=assignment.requirement_id,
            resource_ids=merged_ids,
            unassigned_count=unassigned_count,
            estimated_cost=new_cost + consumed_cost,
        )
        merged_assignments.append(merged_assignment)
        merged_cost += merged_assignment.estimated_cost

    return PlannerResult(
        plan_id=planner_result.plan_id,
        solver=planner_result.solver,
        assignments=merged_assignments,
        estimated_cost=merged_cost,
        duration_ms=planner_result.duration_ms,
        fallback_reason=planner_result.fallback_reason,
    )


def _build_gap_resolution_guidance(
    *,
    db: Session,
    event: Event,
    event_id: str,
    assignments: list[PlannerAssignment],
    requirements: dict[str, PlannerRequirement],
) -> GapResolutionGuidance | None:
    requirement_gaps: list[RequirementGapSummary] = []
    for assignment in assignments:
        if assignment.unassigned_count <= 0:
            continue
        requirement = requirements.get(assignment.requirement_id)
        resource_type = requirement.resource_type if requirement is not None else "unknown"
        requirement_gaps.append(
            RequirementGapSummary(
                requirement_id=assignment.requirement_id,
                resource_type=resource_type,
                missing_count=assignment.unassigned_count,
                message=(
                    f"Missing {assignment.unassigned_count} resource(s) of type "
                    f"{resource_type} for requirement {assignment.requirement_id}."
                ),
            )
        )

    if not requirement_gaps:
        return None

    augment_option = GapResolutionOption(
        option_type="augment_resources",
        title="Fill resource gaps",
        description=(
            "Add missing people, equipment, vehicles or their availability in the database, "
            "then run the planner again."
        ),
        steps=[
            "Add missing resources, for example rented equipment or temporary staff.",
            "Add availability windows for the new resources.",
            "Run event planning again.",
        ],
        endpoints=[
            "/api/resources/people",
            "/api/resources/equipment",
            "/api/resources/vehicles",
            "/api/resources/people/{person_id}/availability",
            "/api/resources/equipment/{equipment_id}/availability",
            "/api/resources/vehicles/{vehicle_id}/availability",
            "/api/planner/generate-plan",
        ],
    )
    reschedule_option = GapResolutionOption(
        option_type="reschedule_event",
        title="Przeloz event na inny termin",
        description=(
            "Przesun planowany termin eventu i uruchom planner ponownie, "
            "aby znalezc okno bez luk."
        ),
        steps=[
            "Zmien planned_start/planned_end eventu w API events.",
            "Uruchom ponownie planner i sprawdz, czy luki zniknely.",
        ],
        endpoints=[
            f"/api/events/{event_id}",
            "/api/planner/generate-plan",
        ],
    )
    return GapResolutionGuidance(
        has_gaps=True,
        requirement_gaps=requirement_gaps,
        options=[augment_option, reschedule_option],
        suggested_reschedule_windows=_suggest_reschedule_windows(
            db=db,
            event=event,
            requirements=requirements,
        ),
    )


def _suggest_reschedule_windows(
    *,
    db: Session,
    event: Event,
    requirements: dict[str, PlannerRequirement],
) -> list[SuggestedRescheduleWindow]:
    del db
    del requirements
    duration = max(event.planned_end - event.planned_start, timedelta(hours=1))
    base = to_utc(event.planned_start) or event.planned_start
    windows: list[SuggestedRescheduleWindow] = []
    for offset_days in (1, 2, 3):
        start = base + timedelta(days=offset_days)
        end = start + duration
        score = Decimal("0.70") - Decimal(str(offset_days - 1)) * Decimal("0.05")
        windows.append(
            SuggestedRescheduleWindow(
                planned_start=start,
                planned_end=end,
                score=score.quantize(Decimal("0.00")),
                note=(
                    "Proponowane okno do szybkiego rerunu planera; "
                    "potwierdz dostepnosc zasobow po zmianie."
                ),
            )
        )
    return windows


def _response_assignment(
    assignment: PlannerAssignment,
    requirements: dict[str, PlannerRequirement],
) -> GeneratedPlanAssignment:
    requirement = requirements[assignment.requirement_id]
    return GeneratedPlanAssignment(
        requirement_id=assignment.requirement_id,
        resource_type=requirement.resource_type,
        resource_ids=assignment.resource_ids,
        unassigned_count=assignment.unassigned_count,
        estimated_cost=_money(assignment.estimated_cost),
    )


def _metric_feature_for_event(event: Event) -> _MetricEventFeature:
    location = event.location
    return _MetricEventFeature(
        feature_attendee_count=event.attendee_count,
        feature_setup_complexity_score=getattr(location, "setup_complexity_score", 1) if location else 1,
        feature_access_difficulty=getattr(location, "access_difficulty", 1) if location else 1,
        feature_parking_difficulty=getattr(location, "parking_difficulty", 1) if location else 1,
    )


def _plan_metrics(
    *,
    event: Event,
    event_feature,
    result: PlannerResult,
    planner_input: PlannerInput,
    optimization_score: Decimal | None = None,
) -> PlanMetrics:
    total_required = sum(max(requirement.quantity, 0) for requirement in planner_input.requirements)
    assigned_count = sum(len(assignment.resource_ids) for assignment in result.assignments)
    missing_count = sum(assignment.unassigned_count for assignment in result.assignments)
    coverage_ratio = Decimal("1.0000")
    if total_required > 0:
        coverage_ratio = _ratio_decimal(Decimal(assigned_count), Decimal(total_required))
    base_duration = Decimal(max(_event_duration_minutes(event), 1))
    estimated_duration = _candidate_duration_minutes(
        base_duration_minutes=base_duration,
        coverage_ratio=coverage_ratio,
        estimated_cost=result.estimated_cost,
    )
    estimated_duration = (
        estimated_duration
        + _max_assignment_travel_minutes(result.assignments, planner_input) * Decimal("0.30")
    ).quantize(Decimal("0.0001"))
    delay_risk = _candidate_delay_risk(
        predicted_duration_minutes=estimated_duration,
        event=event,
        coverage_ratio=coverage_ratio,
        unassigned_count=missing_count,
        total_required=total_required,
    )
    incident_risk = _candidate_incident_risk(
        event_feature=event_feature,
        coverage_ratio=coverage_ratio,
        unassigned_count=missing_count,
        risk_bias=Decimal("0"),
    )
    sla_risk = _candidate_sla_risk(
        delay_risk=delay_risk,
        incident_risk=incident_risk,
        event=event,
        predicted_total_duration_minutes=estimated_duration,
    )
    score = optimization_score
    if score is None:
        score = _plan_score(
            estimated_cost=result.estimated_cost,
            total_duration_minutes=estimated_duration,
            delay_risk=delay_risk,
            incident_risk=incident_risk,
            sla_breach_risk=sla_risk,
            coverage_ratio=coverage_ratio,
            ml_quality_score=Decimal("0"),
            profile={"reliability_bias": 0.0},
        )
    resource_cost_to_budget_ratio = _resource_cost_to_budget_ratio(
        estimated_cost=result.estimated_cost,
        event_budget=event.budget_estimate,
    )
    return PlanMetrics(
        event_budget=_money(event.budget_estimate) if event.budget_estimate is not None else None,
        resource_cost_to_budget_ratio=(
            resource_cost_to_budget_ratio.quantize(Decimal("0.0001"))
            if resource_cost_to_budget_ratio is not None
            else None
        ),
        estimated_cost=_money(result.estimated_cost),
        estimated_duration_minutes=estimated_duration.quantize(Decimal("0.0001")),
        predicted_delay_risk=delay_risk.quantize(Decimal("0.0001")),
        predicted_incident_risk=incident_risk.quantize(Decimal("0.0001")),
        predicted_sla_breach_risk=sla_risk.quantize(Decimal("0.0001")),
        coverage_ratio=coverage_ratio.quantize(Decimal("0.0001")),
        reliability_score=_assignment_reliability_score(result.assignments, planner_input).quantize(Decimal("0.0001")),
        backup_coverage_ratio=_backup_coverage_ratio(result.assignments, planner_input).quantize(Decimal("0.0001")),
        missing_resource_count=int(missing_count),
        assigned_resource_count=int(assigned_count),
        optimization_score=score.quantize(Decimal("0.0001")),
    )


def _metric_delta(baseline: PlanMetrics | None, optimized: PlanMetrics | None) -> PlanMetricDelta | None:
    if baseline is None or optimized is None:
        return None
    return PlanMetricDelta(
        estimated_cost=optimized.estimated_cost - baseline.estimated_cost,
        estimated_duration_minutes=optimized.estimated_duration_minutes - baseline.estimated_duration_minutes,
        predicted_delay_risk=optimized.predicted_delay_risk - baseline.predicted_delay_risk,
        predicted_incident_risk=optimized.predicted_incident_risk - baseline.predicted_incident_risk,
        predicted_sla_breach_risk=optimized.predicted_sla_breach_risk - baseline.predicted_sla_breach_risk,
        coverage_ratio=optimized.coverage_ratio - baseline.coverage_ratio,
        resource_cost_to_budget_ratio=(
            optimized.resource_cost_to_budget_ratio - baseline.resource_cost_to_budget_ratio
            if optimized.resource_cost_to_budget_ratio is not None and baseline.resource_cost_to_budget_ratio is not None
            else None
        ),
        reliability_score=optimized.reliability_score - baseline.reliability_score,
        backup_coverage_ratio=optimized.backup_coverage_ratio - baseline.backup_coverage_ratio,
        missing_resource_count=optimized.missing_resource_count - baseline.missing_resource_count,
        assigned_resource_count=optimized.assigned_resource_count - baseline.assigned_resource_count,
        optimization_score=optimized.optimization_score - baseline.optimization_score,
    )


def _plan_stage_breakdown(
    *,
    event: Event,
    event_feature,
    result: PlannerResult,
    planner_input: PlannerInput,
    total_duration_minutes: Decimal | None,
) -> list[PlanStageBreakdown]:
    if total_duration_minutes is None:
        total_required = sum(max(requirement.quantity, 0) for requirement in planner_input.requirements)
        assigned_count = sum(len(assignment.resource_ids) for assignment in result.assignments)
        coverage_ratio = Decimal("1.0000")
        if total_required > 0:
            coverage_ratio = _ratio_decimal(Decimal(assigned_count), Decimal(total_required))
        total_duration_minutes = _candidate_duration_minutes(
            base_duration_minutes=Decimal(max(_event_duration_minutes(event), 1)),
            coverage_ratio=coverage_ratio,
            estimated_cost=result.estimated_cost,
        )

    breakdown = _duration_breakdown(
        event=event,
        event_feature=event_feature,
        total_duration_minutes=total_duration_minutes,
    )
    selected_candidates = _selected_candidates(result.assignments, planner_input)
    max_travel = max(
        [Decimal(candidate.travel_time_minutes or 0) for candidate in selected_candidates],
        default=Decimal("0"),
    )
    transport_total = breakdown["transport_duration_minutes"]
    outbound = max((transport_total * Decimal("0.55")).quantize(Decimal("0.0001")), max_travel)
    inbound = max((transport_total * Decimal("0.45")).quantize(Decimal("0.0001")), (max_travel * Decimal("0.80")).quantize(Decimal("0.0001")))
    setup = breakdown["setup_duration_minutes"]
    teardown = breakdown["teardown_duration_minutes"]
    support = max(total_duration_minutes - outbound - setup - teardown - inbound, Decimal("0")).quantize(Decimal("0.0001"))
    complexity = getattr(event_feature, "feature_setup_complexity_score", None) or getattr(event.location, "setup_complexity_score", 1) or 1
    access = getattr(event_feature, "feature_access_difficulty", None) or getattr(event.location, "access_difficulty", 1) or 1
    return [
        PlanStageBreakdown(
            stage_key="outbound_transport",
            label="Outbound transport",
            duration_minutes=outbound,
            description="Move crew, vehicles and equipment to the venue before setup starts.",
            drivers=_compact_strings([
                f"Longest selected resource travel estimate: {format(int(max_travel), 'd')} min" if max_travel > 0 else "Most selected resources are already close to the venue.",
                f"Venue access difficulty: {access}/5.",
            ]),
        ),
        PlanStageBreakdown(
            stage_key="setup",
            label="Setup",
            duration_minutes=setup,
            description="Unload, build the technical setup and prepare the venue for delivery.",
            drivers=_compact_strings([
                f"Setup complexity score: {complexity}/10.",
                f"Assigned resources: {sum(len(item.resource_ids) for item in result.assignments)}.",
            ]),
        ),
        PlanStageBreakdown(
            stage_key="event_support",
            label="Event support",
            duration_minutes=support,
            description="Operational support while the event is running.",
            drivers=_compact_strings([
                "Higher reliability resources reduce support friction and delay risk.",
                f"Event window: {_event_duration_minutes(event)} min.",
            ]),
        ),
        PlanStageBreakdown(
            stage_key="teardown",
            label="Teardown",
            duration_minutes=teardown,
            description="Pack down equipment, clear the venue and prepare assets for return.",
            drivers=_compact_strings([
                f"Setup complexity also affects teardown: {complexity}/10.",
                "Replacement-ready equipment lowers incident handling overhead.",
            ]),
        ),
        PlanStageBreakdown(
            stage_key="return_transport",
            label="Return transport",
            duration_minutes=inbound,
            description="Return people, vehicles and equipment to their next operating base.",
            drivers=_compact_strings([
                f"Return estimate follows outbound travel and handling with {format(int(inbound), 'd')} min.",
                "Vehicle distance and venue access drive the transport window.",
            ]),
        ),
    ]


def _selected_plan_metrics(*, event: Event, selected: dict[str, Any], result: PlannerResult) -> PlanMetrics:
    assigned_count = sum(len(assignment.resource_ids) for assignment in result.assignments)
    resource_cost_to_budget_ratio = _resource_cost_to_budget_ratio(
        estimated_cost=result.estimated_cost,
        event_budget=event.budget_estimate,
    )
    return PlanMetrics(
        event_budget=_money(event.budget_estimate) if event.budget_estimate is not None else None,
        resource_cost_to_budget_ratio=(
            resource_cost_to_budget_ratio.quantize(Decimal("0.0001"))
            if resource_cost_to_budget_ratio is not None
            else None
        ),
        estimated_cost=_money(result.estimated_cost),
        estimated_duration_minutes=selected["predicted_duration_minutes"].quantize(Decimal("0.0001")),
        predicted_delay_risk=selected["predicted_delay_risk"].quantize(Decimal("0.0001")),
        predicted_incident_risk=selected["predicted_incident_risk"].quantize(Decimal("0.0001")),
        predicted_sla_breach_risk=selected["predicted_sla_breach_risk"].quantize(Decimal("0.0001")),
        coverage_ratio=selected["coverage_ratio"].quantize(Decimal("0.0001")),
        reliability_score=selected.get("reliability_score", Decimal("0")).quantize(Decimal("0.0001")),
        backup_coverage_ratio=selected.get("backup_coverage_ratio", Decimal("0")).quantize(Decimal("0.0001")),
        missing_resource_count=int(selected["unassigned_count"]),
        assigned_resource_count=int(assigned_count),
        optimization_score=selected["plan_score"].quantize(Decimal("0.0001")),
    )


def _build_business_explanation(
    *,
    db: Session,
    event: Event,
    baseline_result: PlannerResult,
    optimized_result: PlannerResult,
    baseline_metrics: PlanMetrics | None,
    optimized_metrics: PlanMetrics | None,
    metric_deltas: PlanMetricDelta | None,
    optimized_input: PlannerInput,
    selected_explanation: str,
) -> PlanBusinessExplanation:
    fallback = _static_fallback_business_explanation(
        db=db,
        event=event,
        baseline_result=baseline_result,
        optimized_result=optimized_result,
        baseline_metrics=baseline_metrics,
        optimized_metrics=optimized_metrics,
        metric_deltas=metric_deltas,
        optimized_input=optimized_input,
        selected_explanation=selected_explanation,
    )
    snapshot = _business_explanation_snapshot(
        db=db,
        event=event,
        baseline_result=baseline_result,
        optimized_result=optimized_result,
        baseline_metrics=baseline_metrics,
        optimized_metrics=optimized_metrics,
        metric_deltas=metric_deltas,
        optimized_input=optimized_input,
        fallback=fallback,
    )
    return _llm_business_explanation(snapshot=snapshot, fallback=fallback) or fallback


def _static_fallback_business_explanation(
    *,
    db: Session,
    event: Event,
    baseline_result: PlannerResult,
    optimized_result: PlannerResult,
    baseline_metrics: PlanMetrics | None,
    optimized_metrics: PlanMetrics | None,
    metric_deltas: PlanMetricDelta | None,
    optimized_input: PlannerInput,
    selected_explanation: str,
) -> PlanBusinessExplanation:
    del selected_explanation
    changed_resources = not _same_resource_sets(baseline_result.assignments, optimized_result.assignments)
    cost_delta = metric_deltas.estimated_cost if metric_deltas else Decimal("0")
    duration_delta = metric_deltas.estimated_duration_minutes if metric_deltas else Decimal("0")
    risk_delta = metric_deltas.predicted_incident_risk if metric_deltas else Decimal("0")
    summary = (
        "The optimized plan changes resource selection and travel and handling assumptions to improve delivery risk."
        if changed_resources
        else "The optimized plan keeps the same resources because baseline assignments are already strong for this data."
    )
    baseline_vs_optimized = (
        f"Compared with baseline, the optimized plan changes assignment cost by {_signed_money(cost_delta)}, "
        f"operating time by {_signed_minutes(duration_delta)} and incident exposure by {_signed_percentage_points(risk_delta)}."
    )
    drivers = _compact_strings([
        "Resource assignments changed." if changed_resources else "Resource assignments stayed the same.",
        "Higher reliability resources reduce operational delay risk." if metric_deltas and metric_deltas.reliability_score > 0 else None,
        "Closer current locations reduce travel and handling friction." if any((candidate.travel_time_minutes or 0) > 0 for candidate in _selected_candidates(optimized_result.assignments, optimized_input)) else None,
        "Backup coverage protects the plan if a selected resource becomes unavailable." if optimized_metrics and optimized_metrics.backup_coverage_ratio > 0 else None,
    ])
    return PlanBusinessExplanation(
        source="static_fallback",
        summary=summary,
        baseline_vs_optimized=baseline_vs_optimized,
        drivers=drivers,
        metric_explanations=_metric_explanations(metric_deltas),
        resource_impact_summary=_resource_impact_summary(
            db=db,
            assignments=optimized_result.assignments,
            planner_input=optimized_input,
        ),
    )


def _business_explanation_snapshot(
    *,
    db: Session,
    event: Event,
    baseline_result: PlannerResult,
    optimized_result: PlannerResult,
    baseline_metrics: PlanMetrics | None,
    optimized_metrics: PlanMetrics | None,
    metric_deltas: PlanMetricDelta | None,
    optimized_input: PlannerInput,
    fallback: PlanBusinessExplanation,
) -> dict[str, Any]:
    return {
        "event": {
            "name": event.event_name,
            "type": event.event_type,
            "subtype": event.event_subtype,
            "attendees": event.attendee_count,
            "priority": event.priority.value if hasattr(event.priority, "value") else str(event.priority),
            "venue": _location_label(event.location),
            "budget": str(event.budget_estimate) if event.budget_estimate is not None else None,
        },
        "baseline": {
            "metrics": _jsonable(baseline_metrics.model_dump(mode="json") if baseline_metrics else {}),
            "resources": _assignment_resource_rows(db, baseline_result.assignments, optimized_input),
        },
        "optimized": {
            "metrics": _jsonable(optimized_metrics.model_dump(mode="json") if optimized_metrics else {}),
            "resources": _assignment_resource_rows(db, optimized_result.assignments, optimized_input),
        },
        "metric_deltas": _jsonable(metric_deltas.model_dump(mode="json") if metric_deltas else {}),
        "fallback_payload": fallback.model_dump(mode="json"),
    }


def _llm_business_explanation(
    *,
    snapshot: dict[str, Any],
    fallback: PlanBusinessExplanation,
) -> PlanBusinessExplanation | None:
    settings = get_settings()
    if not settings.ai_azure_llm_enabled:
        return None
    try:
        from app.services.ai_prompt_templates import PromptTemplate
        from app.services.azure_openai_service import AzureOpenAIClient

        prompt = PromptTemplate(
            system=(
                "You generate personalized event planning explanations for an operations manager. "
                "Return strict JSON only. Use concrete event, venue and resource names from the input. "
                "Do not use technical optimizer terms such as profile, plan_score, coverage_ratio, "
                "reliability_first, solver or ORM. Use business language instead."
            ),
            user=(
                "Create concise business copy for the planning UI. Required JSON shape:\n"
                "{"
                "\"summary\": string, "
                "\"baseline_vs_optimized\": string, "
                "\"drivers\": string[], "
                "\"metric_explanations\": [{\"metric_key\": string, \"summary\": string, \"drivers\": string[]}], "
                "\"resource_impact_summary\": [{\"resource_id\": string, \"summary\": string, \"contribution\": string}]"
                "}.\n"
                "Keep all numbers consistent with the input. Mention real resource names in resource summaries. "
                "Replace 'logistics cost' with 'travel and handling cost'.\n\n"
                f"INPUT:\n{json.dumps(snapshot, ensure_ascii=False)}"
            ),
        )
        client = AzureOpenAIClient(settings=settings)
        try:
            completion = client.chat_completion(prompt, max_output_tokens=1200)
        finally:
            client.close()
        data = json.loads(completion.content)
        return fallback.model_copy(
            update={
                "source": "llm",
                "summary": _clean_public_explanation(str(data.get("summary") or fallback.summary)),
                "baseline_vs_optimized": _clean_public_explanation(str(data.get("baseline_vs_optimized") or fallback.baseline_vs_optimized)),
                "drivers": [
                    _clean_public_explanation(str(item))
                    for item in data.get("drivers", fallback.drivers)
                    if str(item).strip()
                ][:6],
                "metric_explanations": _merge_llm_metric_explanations(
                    fallback.metric_explanations,
                    data.get("metric_explanations", []),
                ),
                "resource_impact_summary": _merge_llm_resource_impacts(
                    fallback.resource_impact_summary,
                    data.get("resource_impact_summary", []),
                ),
            }
        )
    except Exception:
        return None


def _location_label(location: Location | None) -> str:
    if location is None:
        return "unknown venue"
    parts = [location.name, location.city]
    return ", ".join(str(part) for part in parts if part)


def _assignment_resource_rows(
    db: Session,
    assignments: list[PlannerAssignment],
    planner_input: PlannerInput,
) -> list[dict[str, Any]]:
    requirement_by_id = {
        requirement.requirement_id: requirement for requirement in planner_input.requirements
    }
    candidates_by_requirement = _candidate_lookup(planner_input)
    rows: list[dict[str, Any]] = []
    for assignment in assignments:
        requirement = requirement_by_id.get(assignment.requirement_id)
        if requirement is None:
            continue
        candidates = candidates_by_requirement.get(assignment.requirement_id, {})
        for resource_id in assignment.resource_ids:
            candidate = candidates.get(resource_id)
            rows.append(
                {
                    "resource_id": resource_id,
                    "resource_name": _resource_name(db, requirement.resource_type, resource_id),
                    "resource_type": requirement.resource_type,
                    "distance_to_event_km": str(candidate.distance_to_event_km) if candidate and candidate.distance_to_event_km is not None else None,
                    "travel_time_minutes": candidate.travel_time_minutes if candidate else None,
                    "travel_and_handling_cost": str(_money(candidate.logistics_cost)) if candidate else "0.00",
                    "recommendation_score": str(candidate.score) if candidate else None,
                    "reliability_score": str(candidate.reliability_score) if candidate else None,
                    "location_note": candidate.location_note if candidate else None,
                }
            )
    return rows


def _merge_llm_metric_explanations(
    fallback_items: list[MetricExplanation],
    llm_items: Any,
) -> list[MetricExplanation]:
    by_key = {
        str(item.get("metric_key")): item
        for item in llm_items
        if isinstance(item, dict) and item.get("metric_key")
    } if isinstance(llm_items, list) else {}
    merged: list[MetricExplanation] = []
    for fallback in fallback_items:
        item = by_key.get(fallback.metric_key, {})
        summary = _clean_public_explanation(str(item.get("summary") or fallback.summary))
        drivers = [
            _clean_public_explanation(str(driver))
            for driver in item.get("drivers", fallback.drivers)
            if str(driver).strip()
        ] if isinstance(item.get("drivers", fallback.drivers), list) else fallback.drivers
        merged.append(fallback.model_copy(update={"summary": summary, "drivers": drivers[:5]}))
    return merged


def _merge_llm_resource_impacts(
    fallback_items: list[ResourceImpactItem],
    llm_items: Any,
) -> list[ResourceImpactItem]:
    by_id = {
        str(item.get("resource_id")): item
        for item in llm_items
        if isinstance(item, dict) and item.get("resource_id")
    } if isinstance(llm_items, list) else {}
    merged: list[ResourceImpactItem] = []
    for fallback in fallback_items:
        item = by_id.get(fallback.resource_id, {})
        summary = _clean_public_explanation(str(item.get("summary") or fallback.summary))
        contribution = _clean_public_explanation(str(item.get("contribution") or fallback.contribution))
        merged.append(fallback.model_copy(update={"summary": summary, "contribution": contribution}))
    return merged


def _clean_public_explanation(value: str) -> str:
    replacements = {
        "profile reliability_first": "the reliability-focused option",
        "profile balanced": "the balanced option",
        "profile low_cost": "the cost-conscious option",
        "profile coverage_guarded": "the coverage-focused option",
        "reliability_first": "the reliability-focused option",
        "coverage_guarded": "the coverage-focused option",
        "low_cost": "the cost-conscious option",
        "plan_score": "plan quality",
        "coverage_ratio": "requirement coverage",
        "logistics cost": "travel and handling cost",
        "logistics": "travel and handling",
        "solver": "planning method",
        "ORM": "baseline planning draft",
    }
    cleaned = value
    for source, replacement in replacements.items():
        cleaned = cleaned.replace(source, replacement)
    return cleaned.strip()


def _metric_explanations(metric_deltas: PlanMetricDelta | None) -> list[MetricExplanation]:
    return [
        MetricExplanation(
            metric_key="estimated_cost",
            label="Planned resource cost",
            summary="Assignable people, equipment and vehicle cost for this plan. It does not include the full commercial event budget.",
            drivers=["Hourly rates", "travel and handling cost", "number of assigned slots"],
            delta_direction=_cost_direction(metric_deltas.estimated_cost if metric_deltas else Decimal("0")),
        ),
        MetricExplanation(
            metric_key="estimated_duration_minutes",
            label="Estimated duration",
            summary="Operational time needed for transport, setup, live support, teardown and return travel and handling.",
            drivers=["venue complexity", "resource travel time", "resource reliability", "coverage gaps"],
            delta_direction=_negative_is_better(metric_deltas.estimated_duration_minutes if metric_deltas else Decimal("0")),
        ),
        MetricExplanation(
            metric_key="predicted_delay_risk",
            label="Delay risk",
            summary="Probability-like signal that the plan may run late versus the event window.",
            drivers=["travel distance", "setup complexity", "unassigned resources", "historical reliability"],
            delta_direction=_negative_is_better(metric_deltas.predicted_delay_risk if metric_deltas else Decimal("0")),
        ),
        MetricExplanation(
            metric_key="predicted_incident_risk",
            label="Incident risk",
            summary="Operational risk of issues such as equipment failure, staff pressure or venue friction.",
            drivers=["backup coverage", "resource reliability", "access difficulty", "parking difficulty"],
            delta_direction=_negative_is_better(metric_deltas.predicted_incident_risk if metric_deltas else Decimal("0")),
        ),
        MetricExplanation(
            metric_key="coverage_ratio",
            label="Requirement coverage",
            summary="Share of required resource slots that were assigned.",
            drivers=["available people", "available equipment", "available vehicles"],
            delta_direction=_positive_is_better(metric_deltas.coverage_ratio if metric_deltas else Decimal("0")),
        ),
        MetricExplanation(
            metric_key="reliability_score",
            label="Reliability score",
            summary="Average reliability signal of selected resources based on notes and historical operating patterns.",
            drivers=["seniority", "replacement readiness", "low incident history"],
            delta_direction=_positive_is_better(metric_deltas.reliability_score if metric_deltas else Decimal("0")),
        ),
        MetricExplanation(
            metric_key="backup_coverage_ratio",
            label="Backup coverage",
            summary="How many required slots have realistic alternative resources available if the selected resource fails.",
            drivers=["candidate pool depth", "availability windows", "resource category"],
            delta_direction=_positive_is_better(metric_deltas.backup_coverage_ratio if metric_deltas else Decimal("0")),
        ),
    ]


def _resource_impact_summary(
    *,
    db: Session,
    assignments: list[PlannerAssignment],
    planner_input: PlannerInput,
) -> list[ResourceImpactItem]:
    requirement_by_id = {requirement.requirement_id: requirement for requirement in planner_input.requirements}
    candidates_by_requirement = _candidate_lookup(planner_input)
    rows: list[ResourceImpactItem] = []
    for assignment in assignments:
        requirement = requirement_by_id.get(assignment.requirement_id)
        if requirement is None:
            continue
        for resource_id in assignment.resource_ids:
            candidate = candidates_by_requirement.get(assignment.requirement_id, {}).get(resource_id)
            if candidate is None:
                continue
            rows.append(
                ResourceImpactItem(
                    resource_id=resource_id,
                    resource_name=_resource_name(db, requirement.resource_type, resource_id),
                    resource_type=requirement.resource_type,
                    distance_to_event_km=candidate.distance_to_event_km,
                    travel_time_minutes=candidate.travel_time_minutes,
                    logistics_cost=_money(candidate.logistics_cost),
                    summary=_resource_impact_sentence(candidate),
                    contribution=_candidate_rationale(candidate),
                )
            )
    rows.sort(key=lambda item: (-(item.travel_time_minutes or 0), -float(item.logistics_cost)))
    return rows[:8]


def _same_resource_sets(left: list[PlannerAssignment], right: list[PlannerAssignment]) -> bool:
    left_set = sorted(sorted(item.resource_ids) for item in left)
    right_set = sorted(sorted(item.resource_ids) for item in right)
    return left_set == right_set


def _resource_impact_sentence(candidate: PlannerCandidate) -> str:
    parts = []
    if candidate.distance_to_event_km is not None:
        parts.append(f"{_distance_label(candidate.distance_to_event_km)} from venue")
    if candidate.travel_time_minutes is not None:
        parts.append(f"{candidate.travel_time_minutes} min travel")
    if candidate.logistics_cost > 0:
        parts.append(f"{_money(candidate.logistics_cost)} PLN travel and handling cost")
    if candidate.reliability_score > 0:
        parts.append("positive reliability signal")
    return "; ".join(parts) if parts else "No material travel or handling impact."


def _distance_label(distance_km: Decimal) -> str:
    if distance_km <= Decimal("0"):
        return "on-site"
    if distance_km < Decimal("1"):
        meters = int((distance_km * Decimal("1000")).quantize(Decimal("1")))
        return f"{meters} m"
    return f"{distance_km} km"


def _cost_direction(delta: Decimal) -> str:
    return "better" if delta < 0 else "worse" if delta > 0 else "neutral"


def _negative_is_better(delta: Decimal) -> str:
    return "better" if delta < 0 else "worse" if delta > 0 else "neutral"


def _positive_is_better(delta: Decimal) -> str:
    return "better" if delta > 0 else "worse" if delta < 0 else "neutral"


def _signed_money(value: Decimal) -> str:
    return f"{'+' if value > 0 else ''}{_money(value)} PLN"


def _signed_minutes(value: Decimal) -> str:
    return f"{'+' if value > 0 else ''}{value.quantize(Decimal('0.0001'))} min"


def _signed_percentage_points(value: Decimal) -> str:
    points = (value * Decimal("100")).quantize(Decimal("0.01"))
    return f"{'+' if points > 0 else ''}{points} pp"


def _assignment_slots(
    *,
    db: Session,
    event: Event,
    result: PlannerResult,
    planner_input: PlannerInput,
) -> list[AssignmentSlot]:
    requirement_by_id = {requirement.requirement_id: requirement for requirement in planner_input.requirements}
    assignment_by_requirement = {assignment.requirement_id: assignment for assignment in result.assignments}
    slots: list[AssignmentSlot] = []
    for requirement in planner_input.requirements:
        assignment = assignment_by_requirement.get(requirement.requirement_id)
        selected_ids = list(assignment.resource_ids if assignment else [])
        candidate_options = [
            _candidate_option(db=db, event=event, requirement=requirement, candidate=candidate)
            for candidate in _ranked_slot_candidates(requirement)
        ]
        option_cost_by_id = {
            option.resource_id: option.estimated_cost
            for option in candidate_options
        }
        for index in range(max(requirement.quantity, 1)):
            selected_resource_id = selected_ids[index] if index < len(selected_ids) else None
            selected_estimated_cost = Decimal("0.00")
            if selected_resource_id:
                selected_estimated_cost = option_cost_by_id.get(selected_resource_id, Decimal("0.00"))
                if selected_estimated_cost == Decimal("0.00") and assignment is not None:
                    selected_estimated_cost = _money(_resource_cost_share(assignment))
            slots.append(
                AssignmentSlot(
                    requirement_id=requirement.requirement_id,
                    slot_index=index + 1,
                    resource_type=requirement.resource_type,
                    business_label=_slot_label(requirement, index + 1),
                    selected_resource_id=selected_resource_id,
                    selected_resource_name=_resource_name(db, requirement.resource_type, selected_resource_id) if selected_resource_id else None,
                    estimated_cost=selected_estimated_cost,
                    candidate_options=candidate_options,
                )
            )
    return slots


def _ranked_slot_candidates(requirement: PlannerRequirement) -> list[PlannerCandidate]:
    return sorted(requirement.candidates, key=lambda item: (-item.score, item.cost_per_hour, item.resource_id))


def _candidate_option(
    *,
    db: Session,
    event: Event,
    requirement: PlannerRequirement,
    candidate: PlannerCandidate,
) -> AssignmentCandidateOption:
    score = min(max(candidate.score * Decimal("100"), Decimal("0")), Decimal("100"))
    cost = _money(candidate.cost_per_hour * _planner_requirement_hours(event, requirement))
    return AssignmentCandidateOption(
        resource_id=candidate.resource_id,
        resource_name=_resource_name(db, requirement.resource_type, candidate.resource_id),
        recommendation_score=score.quantize(Decimal("0.01")),
        estimated_cost=cost,
        distance_to_event_km=candidate.distance_to_event_km,
        travel_time_minutes=candidate.travel_time_minutes,
        logistics_cost=_money(candidate.logistics_cost),
        location_match_score=candidate.location_match_score.quantize(Decimal("0.0001")),
        location_note=candidate.location_note,
        availability_note="Available for the required event window.",
        why_recommended=_candidate_rationale(candidate),
    )


def _candidate_rationale(candidate: PlannerCandidate) -> str:
    location = ""
    if candidate.travel_time_minutes is not None:
        location = f" Travel estimate: {candidate.travel_time_minutes} min."
    if candidate.reliability_score >= Decimal("0.20"):
        return f"Strong reliability history for event-critical work.{location}"
    if candidate.reliability_score > Decimal("0"):
        return f"Good reliability profile with acceptable cost.{location}"
    return f"Cost-effective available resource for this requirement.{location}"


def _slot_label(requirement: PlannerRequirement, slot_index: int) -> str:
    base = requirement.resource_type.replace("_", " ").title()
    return f"{base} {slot_index}"


def _resource_name(db: Session, resource_type: str, resource_id: str | None) -> str:
    if not resource_id:
        return "No resource selected"
    if resource_type == "person":
        person = db.get(ResourcePerson, resource_id)
        return person.full_name if person is not None else "Unknown person"
    if resource_type == "equipment":
        equipment = db.get(Equipment, resource_id)
        if equipment is None:
            return "Unknown equipment"
        type_name = equipment.equipment_type.type_name if equipment.equipment_type else "Equipment"
        return f"{type_name}{f' - {equipment.asset_tag}' if equipment.asset_tag else ''}"
    if resource_type == "vehicle":
        vehicle = db.get(Vehicle, resource_id)
        return vehicle.vehicle_name if vehicle is not None else "Unknown vehicle"
    return resource_id


def _planner_requirement_hours(event: Event, requirement: PlannerRequirement) -> Decimal:
    start = requirement.required_start or event.planned_start
    end = requirement.required_end or event.planned_end
    seconds = max((end - start).total_seconds(), 0)
    return Decimal(str(seconds / 3600.0))


def _assignment_resource_type(requirement: PlannerRequirement) -> AssignmentResourceType:
    if requirement.resource_type == "person":
        return AssignmentResourceType.person
    if requirement.resource_type == "equipment":
        return AssignmentResourceType.equipment
    if requirement.resource_type == "vehicle":
        return AssignmentResourceType.vehicle
    raise PlanGenerationError(f"Unsupported resource type: {requirement.resource_type}")


def _resource_fk(resource_type: str, resource_id: str) -> dict[str, str]:
    if resource_type == "person":
        return {"person_id": resource_id}
    if resource_type == "equipment":
        return {"equipment_id": resource_id}
    if resource_type == "vehicle":
        return {"vehicle_id": resource_id}
    raise PlanGenerationError(f"Unsupported resource type: {resource_type}")


def _assignment_role(requirement: PlannerRequirement) -> str:
    return f"requirement:{requirement.requirement_id}"


def _extract_requirement_id_from_role(assignment_role: str | None) -> str | None:
    if not assignment_role:
        return None
    prefix = "requirement:"
    if not assignment_role.startswith(prefix):
        return None
    requirement_id = assignment_role[len(prefix):].strip()
    if not requirement_id:
        return None
    return requirement_id


def _assignment_resource_id(assignment: Assignment) -> str | None:
    if assignment.resource_type == AssignmentResourceType.person:
        return assignment.person_id
    if assignment.resource_type == AssignmentResourceType.equipment:
        return assignment.equipment_id
    if assignment.resource_type == AssignmentResourceType.vehicle:
        return assignment.vehicle_id
    return None


def _assignment_estimated_cost(db: Session, assignment: Assignment) -> Decimal:
    duration_seconds = max((assignment.planned_end - assignment.planned_start).total_seconds(), 0)
    duration_hours = Decimal(str(duration_seconds / 3600.0))
    if assignment.resource_type == AssignmentResourceType.person and assignment.person_id:
        person = db.get(ResourcePerson, assignment.person_id)
        if person is not None and person.cost_per_hour is not None:
            return _money(person.cost_per_hour * duration_hours)
    if assignment.resource_type == AssignmentResourceType.equipment and assignment.equipment_id:
        equipment = db.get(Equipment, assignment.equipment_id)
        if equipment is not None and equipment.hourly_cost_estimate is not None:
            return _money(equipment.hourly_cost_estimate * duration_hours)
    if assignment.resource_type == AssignmentResourceType.vehicle and assignment.vehicle_id:
        vehicle = db.get(Vehicle, assignment.vehicle_id)
        if vehicle is not None and vehicle.cost_per_hour is not None:
            return _money(vehicle.cost_per_hour * duration_hours)
    return Decimal("0.00")


def _resource_cost_share(assignment: PlannerAssignment) -> Decimal:
    if not assignment.resource_ids:
        return Decimal("0")
    return assignment.estimated_cost / Decimal(len(assignment.resource_ids))


def _resource_cost_to_budget_ratio(
    *,
    estimated_cost: Decimal,
    event_budget: Decimal | None,
) -> Decimal | None:
    if event_budget is None or event_budget <= 0:
        return None
    return (estimated_cost / event_budget).quantize(Decimal("0.0001"))


def _candidate_lookup(planner_input: PlannerInput) -> dict[str, dict[str, PlannerCandidate]]:
    return {
        requirement.requirement_id: {
            candidate.resource_id: candidate
            for candidate in requirement.candidates
        }
        for requirement in planner_input.requirements
    }


def _assignment_reliability_score(
    assignments: list[PlannerAssignment],
    planner_input: PlannerInput,
) -> Decimal:
    candidates_by_requirement = _candidate_lookup(planner_input)
    values: list[Decimal] = []
    for assignment in assignments:
        candidates = candidates_by_requirement.get(assignment.requirement_id, {})
        for resource_id in assignment.resource_ids:
            candidate = candidates.get(resource_id)
            if candidate is not None:
                values.append(max(candidate.reliability_score, Decimal("0")))
    if not values:
        return Decimal("0.0000")
    return (sum(values, Decimal("0")) / Decimal(len(values))).quantize(Decimal("0.0001"))


def _selected_candidates(
    assignments: list[PlannerAssignment],
    planner_input: PlannerInput,
) -> list[PlannerCandidate]:
    candidates_by_requirement = _candidate_lookup(planner_input)
    selected: list[PlannerCandidate] = []
    for assignment in assignments:
        candidates = candidates_by_requirement.get(assignment.requirement_id, {})
        for resource_id in assignment.resource_ids:
            candidate = candidates.get(resource_id)
            if candidate is not None:
                selected.append(candidate)
    return selected


def _max_assignment_travel_minutes(
    assignments: list[PlannerAssignment],
    planner_input: PlannerInput,
) -> Decimal:
    return max(
        [Decimal(candidate.travel_time_minutes or 0) for candidate in _selected_candidates(assignments, planner_input)],
        default=Decimal("0"),
    )


def _backup_coverage_ratio(
    assignments: list[PlannerAssignment],
    planner_input: PlannerInput,
) -> Decimal:
    assignment_by_requirement = {
        assignment.requirement_id: assignment
        for assignment in assignments
    }
    backed_slots = Decimal("0")
    total_slots = Decimal("0")
    for requirement in planner_input.requirements:
        required_quantity = max(requirement.quantity, 0)
        if required_quantity <= 0:
            continue
        total_slots += Decimal(required_quantity)
        assignment = assignment_by_requirement.get(requirement.requirement_id)
        selected_ids = set(assignment.resource_ids if assignment else [])
        backup_count = len([
            candidate
            for candidate in requirement.candidates
            if candidate.resource_id not in selected_ids
        ])
        backed_slots += Decimal(min(required_quantity, backup_count))
    if total_slots <= 0:
        return Decimal("0.0000")
    return (backed_slots / total_slots).quantize(Decimal("0.0001"))


def _compact_strings(values: list[str | None]) -> list[str]:
    return [value for value in values if value]


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _event_duration_minutes(event: Event) -> int:
    seconds = (event.planned_end - event.planned_start).total_seconds()
    return int(max(seconds, 0) // 60)


def _risk_from_unassigned(assignments: list[PlannerAssignment]) -> Decimal:
    unassigned = sum(assignment.unassigned_count for assignment in assignments)
    return Decimal(str(unassigned))


def _recommendation_rationale(assignments: list[PlannerAssignment]) -> str:
    if _is_fully_assigned(assignments):
        return "All requirements assigned by deterministic planner."
    unassigned = sum(assignment.unassigned_count for assignment in assignments)
    return f"Partial plan generated with {unassigned} unassigned resource slot(s)."


def _run_notes(assignments: list[PlannerAssignment]) -> str:
    if _is_fully_assigned(assignments):
        return "Planner completed with full assignment coverage."
    unassigned = sum(assignment.unassigned_count for assignment in assignments)
    return f"Planner completed with {unassigned} unassigned resource slot(s)."


def _is_fully_assigned(assignments: list[PlannerAssignment]) -> bool:
    return all(assignment.unassigned_count == 0 for assignment in assignments)


def _assigned_vehicle_ids(
    assignments: list[PlannerAssignment],
    requirements: dict[str, PlannerRequirement],
) -> list[str]:
    vehicle_ids: list[str] = []
    for assignment in assignments:
        requirement = requirements[assignment.requirement_id]
        if requirement.resource_type == "vehicle":
            vehicle_ids.extend(assignment.resource_ids)
    return vehicle_ids


def _first_driver(
    db: Session,
    assignments: list[PlannerAssignment],
    requirements: dict[str, PlannerRequirement],
) -> str | None:
    for assignment in assignments:
        requirement = requirements[assignment.requirement_id]
        if requirement.resource_type != "person":
            continue
        for person_id in assignment.resource_ids:
            person = db.get(ResourcePerson, person_id)
            if (
                person is not None
                and getattr(person.role, "value", person.role) == "driver"
            ):
                return person.person_id
    return None


def _distance_km(origin: Location, destination: Location) -> Decimal | None:
    if (
        origin.latitude is None
        or origin.longitude is None
        or destination.latitude is None
        or destination.longitude is None
    ):
        return None

    lat1 = radians(float(origin.latitude))
    lon1 = radians(float(origin.longitude))
    lat2 = radians(float(destination.latitude))
    lon2 = radians(float(destination.longitude))

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    haversine = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    distance = 6371.0 * 2 * asin(sqrt(haversine))
    return Decimal(str(round(distance, 2)))


def _transport_duration_minutes(distance: Decimal | None) -> int:
    if distance is None:
        return 60
    if distance <= Decimal("0"):
        return 0
    if distance < Decimal("0.25"):
        return 3
    if distance < Decimal("1"):
        return 5
    return max(int((distance / Decimal("50")) * Decimal("60")), 15)


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _proposal_profiles() -> list[dict[str, float | str]]:
    return [
        {
            "name": "balanced",
            "score_weight": 1.00,
            "cost_weight": 0.020,
            "reliability_bias": 0.00,
            "risk_bias": 0.00,
        },
        {
            "name": "low_cost",
            "score_weight": 0.82,
            "cost_weight": 0.050,
            "reliability_bias": -0.04,
            "risk_bias": 0.08,
        },
        {
            "name": "reliability_first",
            "score_weight": 1.24,
            "cost_weight": 0.015,
            "reliability_bias": 0.35,
            "risk_bias": -0.10,
        },
        {
            "name": "coverage_guarded",
            "score_weight": 1.12,
            "cost_weight": 0.022,
            "reliability_bias": 0.18,
            "risk_bias": -0.04,
        },
    ]


def _apply_profile_to_planner_input(
    *,
    planner_input: PlannerInput,
    score_weight: float,
    cost_weight: float,
    reliability_bias: float,
    risk_bias: float,
) -> PlannerInput:
    transformed_requirements: list[PlannerRequirement] = []
    for requirement in planner_input.requirements:
        transformed_candidates: list[PlannerCandidate] = []
        for candidate in requirement.candidates:
            base_score = float(candidate.score)
            reliability_score = float(candidate.reliability_score)
            cost_penalty = (float(candidate.cost_per_hour) / 100.0) * cost_weight
            location_score = float(candidate.location_match_score or Decimal("1"))
            reliability_weight = max(0.0, 0.15 + reliability_bias * 2.5 - risk_bias * 0.4)
            logistics_weight = max(0.0, 0.10 + reliability_bias * 0.55 - risk_bias * 0.20)
            adjusted_score = max(
                base_score * score_weight
                + reliability_score * reliability_weight
                + location_score * logistics_weight
                - cost_penalty,
                0.0001,
            )
            transformed_candidates.append(
                PlannerCandidate(
                    resource_id=candidate.resource_id,
                    cost_per_hour=candidate.cost_per_hour,
                    score=Decimal(str(round(adjusted_score, 6))),
                    reliability_score=candidate.reliability_score,
                    distance_to_event_km=candidate.distance_to_event_km,
                    travel_time_minutes=candidate.travel_time_minutes,
                    logistics_cost=candidate.logistics_cost,
                    location_match_score=candidate.location_match_score,
                    location_note=candidate.location_note,
                    available_from=candidate.available_from,
                    available_to=candidate.available_to,
                )
            )
        transformed_requirements.append(
            PlannerRequirement(
                requirement_id=requirement.requirement_id,
                resource_type=requirement.resource_type,
                quantity=requirement.quantity,
                mandatory=requirement.mandatory,
                required_start=requirement.required_start,
                required_end=requirement.required_end,
                candidates=transformed_candidates,
            )
        )
    return PlannerInput(requirements=transformed_requirements)


def _resolve_model_artifact(
    *,
    db: Session,
    prediction_type: PredictionType,
    preferred_model_id: str | None,
) -> dict[str, Any]:
    model = None
    if preferred_model_id:
        model = db.get(ModelRegistry, preferred_model_id)
        if model is None:
            raise PlanGenerationError("Requested model_id was not found.")
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
        raise PlanGenerationError("Active duration model not found for CP-07 proposal.")

    artifact_path = (model.metrics or {}).get("artifact_path")
    if not artifact_path:
        raise PlanGenerationError("Model artifact path missing in active duration model.")
    return _load_artifact(artifact_path)


def _resolve_plan_evaluator_artifact(
    *,
    db: Session,
    preferred_model_id: str | None,
) -> dict[str, Any] | None:
    model = None
    if preferred_model_id:
        model = db.get(ModelRegistry, preferred_model_id)
    else:
        model = (
            db.query(ModelRegistry)
            .filter(
                ModelRegistry.model_name == "plan_candidate_evaluator",
                ModelRegistry.prediction_type == PredictionType.other,
                ModelRegistry.status == ModelStatus.active,
            )
            .order_by(ModelRegistry.created_at.desc())
            .first()
        )
    if model is None:
        return None
    artifact_path = (model.metrics or {}).get("artifact_path")
    if not artifact_path:
        return None
    try:
        artifact = _load_artifact(artifact_path)
    except Exception:
        return None
    if artifact.get("kind") != "plan_evaluator_estimator":
        return None
    return artifact


def _load_artifact(path: str) -> dict[str, Any]:
    artifact_path = Path(path)
    if not artifact_path.exists():
        raise PlanGenerationError(f"Model artifact not found: {path}")
    with artifact_path.open("rb") as handle:
        loaded = pickle.load(handle)
    if not isinstance(loaded, dict):
        raise PlanGenerationError("Model artifact has invalid format.")
    return loaded


def _predict_duration_minutes(
    artifact: dict[str, Any], event_feature: EventFeature
) -> Decimal:
    vector = _duration_feature_vector(event_feature)
    kind = str(artifact.get("kind", ""))
    if kind == "mean_regressor":
        return Decimal(str(artifact.get("mean_value", 0.0))).quantize(Decimal("0.0001"))
    if kind in {"sklearn_linear_regression", "sklearn_estimator"}:
        model = artifact.get("model")
        if model is None:
            raise PlanGenerationError("Duration model artifact missing sklearn model.")
        value = float(model.predict([vector])[0])
        return Decimal(str(max(value, 0.0))).quantize(Decimal("0.0001"))
    raise PlanGenerationError(f"Unsupported duration model artifact kind: {kind}")


def _duration_feature_vector(event_feature: EventFeature) -> list[float]:
    priority = {"low": 1.0, "medium": 2.0, "high": 3.0, "critical": 4.0}.get(
        (event_feature.feature_priority or "medium").lower(), 2.0
    )
    season = {"winter": 1.0, "spring": 2.0, "summer": 3.0, "autumn": 4.0}.get(
        (event_feature.feature_season or "").lower(), 0.0
    )
    return [
        float(event_feature.feature_attendee_count or 0),
        float(event_feature.feature_setup_complexity_score or 0),
        float(event_feature.feature_access_difficulty or 0),
        float(event_feature.feature_parking_difficulty or 0),
        float(event_feature.feature_required_person_count or 0),
        float(event_feature.feature_required_equipment_count or 0),
        float(event_feature.feature_required_vehicle_count or 0),
        priority,
        float(event_feature.feature_day_of_week or 0),
        float(event_feature.feature_month or 0),
        season,
        1.0 if event_feature.feature_requires_transport else 0.0,
        1.0 if event_feature.feature_requires_setup else 0.0,
        1.0 if event_feature.feature_requires_teardown else 0.0,
    ]


def _candidate_duration_minutes(
    *,
    base_duration_minutes: Decimal,
    coverage_ratio: Decimal,
    estimated_cost: Decimal,
) -> Decimal:
    coverage_penalty = (Decimal("1") - coverage_ratio) * Decimal("0.28")
    # Assignment cost alone should not dominate duration. Expensive senior
    # resources often reduce execution time; budget pressure is shown as a
    # separate business metric.
    cost_pressure = min(estimated_cost / Decimal("120000"), Decimal("0.10"))
    multiplier = Decimal("1") + coverage_penalty + cost_pressure
    return (base_duration_minutes * multiplier).quantize(Decimal("0.0001"))


def _candidate_risk(
    *,
    coverage_ratio: Decimal,
    unassigned_count: int,
    total_required: int,
    risk_bias: Decimal,
) -> Decimal:
    if total_required <= 0:
        total_required = 1
    unassigned_ratio = Decimal(unassigned_count) / Decimal(total_required)
    risk = (
        unassigned_ratio * Decimal("0.70")
        + (Decimal("1") - coverage_ratio) * Decimal("0.20")
        + risk_bias
    )
    risk = max(Decimal("0.01"), min(risk, Decimal("0.99")))
    return risk.quantize(Decimal("0.0001"))


def _candidate_quality_score(
    *,
    event_feature: EventFeature,
    coverage_ratio: Decimal,
    unassigned_count: int,
    total_required: int,
    estimated_cost: Decimal,
    predicted_duration_minutes: Decimal,
    predicted_risk: Decimal,
    profile: dict[str, float | str],
    reliability_score: Decimal,
    backup_coverage_ratio: Decimal,
    event_budget: Decimal | None,
    plan_evaluator_artifact: dict[str, Any] | None,
) -> float:
    resource_cost_ratio = _resource_cost_to_budget_ratio(
        estimated_cost=estimated_cost,
        event_budget=event_budget,
    )
    if plan_evaluator_artifact is not None:
        model = plan_evaluator_artifact.get("model")
        if model is not None:
            vector = [
                float(event_feature.feature_attendee_count or 0),
                float(event_feature.feature_setup_complexity_score or 0),
                float(event_feature.feature_access_difficulty or 0),
                float(event_feature.feature_parking_difficulty or 0),
                float(event_feature.feature_required_person_count or 0),
                float(event_feature.feature_required_equipment_count or 0),
                float(event_feature.feature_required_vehicle_count or 0),
                float({"low": 1, "medium": 2, "high": 3, "critical": 4}.get((event_feature.feature_priority or "medium").lower(), 2)),
                float(coverage_ratio),
                float(Decimal(unassigned_count) / max(Decimal("1"), Decimal(total_required))),
                float(estimated_cost / Decimal("1000")),
                float(predicted_duration_minutes / Decimal("60")),
                float(predicted_risk),
                float(profile["score_weight"]),
                float(profile["cost_weight"]),
                float(reliability_score),
                float(backup_coverage_ratio),
                float(resource_cost_ratio or Decimal("0")),
            ]
            expected_features = getattr(model, "n_features_in_", len(vector))
            if int(expected_features) == len(vector):
                score = float(model.predict([vector])[0])
                return max(min(score, 100.0), 0.0)

    # Fallback if plan evaluator model is unavailable.
    cost_component = float(min(estimated_cost / Decimal("70000"), Decimal("1")))
    duration_component = float(min(predicted_duration_minutes / Decimal("900"), Decimal("1")))
    risk_component = float(predicted_risk)
    unassigned_component = float(min(Decimal(unassigned_count) / Decimal("10"), Decimal("1")))
    budget_component = float(min(resource_cost_ratio or Decimal("0"), Decimal("1")))
    score = 100.0
    score -= cost_component * 16.0
    score -= budget_component * 10.0
    score -= duration_component * 25.0
    score -= risk_component * 35.0
    score -= unassigned_component * 20.0
    score += float(coverage_ratio) * 6.0
    score += float(reliability_score) * 14.0
    score += float(backup_coverage_ratio) * 8.0
    return max(min(score, 100.0), 0.0)


def _duration_breakdown(
    *,
    event: Event,
    event_feature: EventFeature,
    total_duration_minutes: Decimal,
) -> dict[str, Decimal]:
    complexity = Decimal(str(float(event_feature.feature_setup_complexity_score or 1)))
    transport_share = Decimal("0.20") if event.requires_transport else Decimal("0.05")
    setup_share = Decimal("0.27") if event.requires_setup else Decimal("0.08")
    teardown_share = Decimal("0.18") if event.requires_teardown else Decimal("0.05")
    # Adjust split with setup complexity to better reflect heavier setups.
    setup_share += min(complexity / Decimal("100"), Decimal("0.10"))
    teardown_share += min(complexity / Decimal("140"), Decimal("0.06"))
    used_share = transport_share + setup_share + teardown_share
    if used_share > Decimal("0.85"):
        scale = Decimal("0.85") / used_share
        transport_share *= scale
        setup_share *= scale
        teardown_share *= scale

    transport = (total_duration_minutes * transport_share).quantize(Decimal("0.0001"))
    setup = (total_duration_minutes * setup_share).quantize(Decimal("0.0001"))
    teardown = (total_duration_minutes * teardown_share).quantize(Decimal("0.0001"))
    return {
        "transport_duration_minutes": max(transport, Decimal("0")),
        "setup_duration_minutes": max(setup, Decimal("0")),
        "teardown_duration_minutes": max(teardown, Decimal("0")),
    }


def _candidate_delay_risk(
    *,
    predicted_duration_minutes: Decimal,
    event: Event,
    coverage_ratio: Decimal,
    unassigned_count: int,
    total_required: int,
) -> Decimal:
    event_window = Decimal(max(_event_duration_minutes(event), 1))
    duration_pressure = max((predicted_duration_minutes / event_window) - Decimal("1"), Decimal("0"))
    unassigned_ratio = Decimal(unassigned_count) / Decimal(max(total_required, 1))
    risk = (
        duration_pressure * Decimal("0.50")
        + (Decimal("1") - coverage_ratio) * Decimal("0.30")
        + unassigned_ratio * Decimal("0.20")
    )
    return min(max(risk, Decimal("0.01")), Decimal("0.99")).quantize(Decimal("0.0001"))


def _candidate_incident_risk(
    *,
    event_feature: EventFeature,
    coverage_ratio: Decimal,
    unassigned_count: int,
    risk_bias: Decimal,
) -> Decimal:
    setup_complexity = Decimal(str(float(event_feature.feature_setup_complexity_score or 1))) / Decimal("10")
    access = Decimal(str(float(event_feature.feature_access_difficulty or 1))) / Decimal("10")
    parking = Decimal(str(float(event_feature.feature_parking_difficulty or 1))) / Decimal("10")
    unassigned_penalty = min(Decimal(unassigned_count) * Decimal("0.05"), Decimal("0.40"))
    risk = (
        setup_complexity * Decimal("0.35")
        + access * Decimal("0.20")
        + parking * Decimal("0.10")
        + (Decimal("1") - coverage_ratio) * Decimal("0.20")
        + unassigned_penalty
        + risk_bias
    )
    return min(max(risk, Decimal("0.01")), Decimal("0.99")).quantize(Decimal("0.0001"))


def _candidate_sla_risk(
    *,
    delay_risk: Decimal,
    incident_risk: Decimal,
    event: Event,
    predicted_total_duration_minutes: Decimal,
) -> Decimal:
    event_window = Decimal(max(_event_duration_minutes(event), 1))
    duration_ratio = predicted_total_duration_minutes / event_window
    breach_pressure = max(duration_ratio - Decimal("1"), Decimal("0"))
    risk = delay_risk * Decimal("0.55") + incident_risk * Decimal("0.35") + breach_pressure * Decimal("0.10")
    return min(max(risk, Decimal("0.01")), Decimal("0.99")).quantize(Decimal("0.0001"))


def _plan_confidence_score(
    *,
    plan_evaluator_artifact: dict[str, Any] | None,
    coverage_ratio: Decimal,
    unassigned_count: int,
) -> Decimal:
    if plan_evaluator_artifact is None:
        base = Decimal("0.68")
    else:
        metrics = (
            plan_evaluator_artifact.get("model_selection", {})
            .get("leaderboard", [{}])[0]
            .get("test_metrics", {})
        )
        mae = Decimal(str(metrics.get("mae_minutes", 1.0)))
        base = Decimal("1") - min(mae / Decimal("20"), Decimal("0.40"))
    penalty = (Decimal("1") - coverage_ratio) * Decimal("0.40") + min(Decimal(unassigned_count) * Decimal("0.04"), Decimal("0.20"))
    confidence = base - penalty
    return min(max(confidence, Decimal("0.05")), Decimal("0.99")).quantize(Decimal("0.0001"))


def _ood_score(event_feature: EventFeature) -> Decimal:
    attendee = Decimal(str(float(event_feature.feature_attendee_count or 0)))
    setup = Decimal(str(float(event_feature.feature_setup_complexity_score or 1)))
    access = Decimal(str(float(event_feature.feature_access_difficulty or 1)))
    parking = Decimal(str(float(event_feature.feature_parking_difficulty or 1)))

    score = Decimal("0")
    if attendee > Decimal("2000"):
        score += Decimal("0.45")
    elif attendee > Decimal("1200"):
        score += Decimal("0.30")
    elif attendee > Decimal("800"):
        score += Decimal("0.15")
    score += max(setup - Decimal("8"), Decimal("0")) * Decimal("0.06")
    score += max(access - Decimal("4"), Decimal("0")) * Decimal("0.05")
    score += max(parking - Decimal("4"), Decimal("0")) * Decimal("0.04")
    return min(score, Decimal("0.99")).quantize(Decimal("0.0001"))


def _plan_score(
    *,
    estimated_cost: Decimal,
    total_duration_minutes: Decimal,
    delay_risk: Decimal,
    incident_risk: Decimal,
    sla_breach_risk: Decimal,
    coverage_ratio: Decimal,
    ml_quality_score: Decimal,
    profile: dict[str, float | str],
) -> Decimal:
    cost_norm = min(estimated_cost / Decimal("100000"), Decimal("1"))
    duration_norm = min(total_duration_minutes / Decimal("1200"), Decimal("1"))
    risk_norm = min((delay_risk + incident_risk + sla_breach_risk) / Decimal("3"), Decimal("1"))

    time_weight = Decimal("0.30")
    cost_weight = Decimal("0.25")
    risk_weight = Decimal("0.45")
    weighted_penalty = (
        duration_norm * time_weight
        + cost_norm * cost_weight
        + risk_norm * risk_weight
    )
    score = Decimal("100") * (Decimal("1") - weighted_penalty)
    # Keep the score inside the 0-100 business scale without flattening all
    # feasible plans to 100. CP-08 compares baseline vs optimized plans, so the
    # ranking must expose meaningful ML/profile differences instead of ties.
    score += (coverage_ratio - Decimal("0.90")) * Decimal("6")
    score += ml_quality_score * Decimal("0.05")
    score += Decimal(str(float(profile["reliability_bias"]))) * Decimal("8")
    score = min(max(score, Decimal("0")), Decimal("100"))
    return score.quantize(Decimal("0.0001"))


def _apply_guardrails(
    *,
    candidate_name: str,
    confidence_score: Decimal,
    ood_score: Decimal,
    delay_risk: Decimal,
    incident_risk: Decimal,
    sla_breach_risk: Decimal,
    settings,
) -> tuple[bool, str | None]:
    if confidence_score < Decimal(str(settings.ml_plan_guardrail_confidence_min)):
        return True, "low_confidence"
    if ood_score > Decimal(str(settings.ml_plan_guardrail_ood_max)):
        return True, "out_of_distribution"
    if max(delay_risk, incident_risk, sla_breach_risk) > Decimal(
        str(settings.ml_plan_guardrail_high_risk_max)
    ):
        if candidate_name != "coverage_guarded":
            return True, "high_risk_switch_to_guarded_profile"
    return False, None


def _selection_explanation(
    *,
    candidate_name: str,
    plan_score: Decimal,
    estimated_cost: Decimal,
    total_duration_minutes: Decimal,
    delay_risk: Decimal,
    incident_risk: Decimal,
    sla_breach_risk: Decimal,
    coverage_ratio: Decimal,
    guardrail_applied: bool,
    guardrail_reason: str | None,
) -> str:
    guardrail_text = (
        f" Guardrail applied: {guardrail_reason}."
        if guardrail_applied and guardrail_reason
        else ""
    )
    return (
        f"Profile {candidate_name} selected with plan_score={plan_score}. "
        f"Cost={_money(estimated_cost)} PLN, total_duration={total_duration_minutes} min, "
        f"delay_risk={delay_risk}, incident_risk={incident_risk}, sla_breach_risk={sla_breach_risk}, "
        f"coverage_ratio={coverage_ratio}."
        f"{guardrail_text}"
    )


def _ratio_decimal(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator <= 0:
        return Decimal("0")
    return (numerator / denominator).quantize(Decimal("0.0001"))


def _other_event_has_priority_over_current(
    *,
    other_event: Event,
    other_status: str,
    current_event: Event,
    current_status: str,
) -> bool:
    other_accepted = other_status in _PRIORITY_ACCEPTED_STATUSES
    current_accepted = current_status in _PRIORITY_ACCEPTED_STATUSES
    if other_accepted and not current_accepted:
        return True
    if current_accepted and not other_accepted:
        return False
    return _event_priority_key(other_event) <= _event_priority_key(current_event)


def _event_priority_key(event: Event) -> tuple[float, str]:
    created_at = event.created_at
    created_ts = created_at.timestamp() if isinstance(created_at, datetime) else 0.0
    return created_ts, event.event_id


def _latest_recommendation_for_event(
    db: Session, event_id: str
) -> PlannerRecommendation | None:
    return (
        db.query(PlannerRecommendation)
        .filter(PlannerRecommendation.event_id == event_id)
        .order_by(PlannerRecommendation.created_at.desc())
        .first()
    )


def _get_event_for_update(db: Session, event_id: str) -> Event | None:
    return (
        db.query(Event)
        .filter(Event.event_id == event_id)
        .with_for_update()
        .first()
    )


def _validate_expected_event_version(
    event: Event,
    expected_event_updated_at: datetime | None,
) -> None:
    if expected_event_updated_at is None:
        return
    current = to_utc(event.updated_at)
    expected = to_utc(expected_event_updated_at)
    if current is None or expected is None:
        return
    if current != expected:
        raise PlanGenerationError(
            "Event changed concurrently. Refresh event state before replanning."
        )


def attach_plan_outcome_feedback(
    db: Session,
    *,
    event_id: str,
    finished_on_time: bool | None,
    total_delay_minutes: int | None,
    actual_cost: Decimal | None,
    sla_breached: bool,
    closed_at: datetime,
) -> None:
    recommendation = _latest_recommendation_for_event(db, event_id)
    if recommendation is None:
        return
    planner_run = db.get(PlannerRun, recommendation.planner_run_id)
    if planner_run is None:
        return

    snapshot = dict(planner_run.input_snapshot or {})
    selected = dict(snapshot.get("selected_candidate") or {})
    selected["actual_outcome"] = {
        "finished_on_time": finished_on_time,
        "total_delay_minutes": total_delay_minutes,
        "actual_cost": str(actual_cost) if actual_cost is not None else None,
        "sla_breached": sla_breached,
        "closed_at": closed_at.isoformat(),
    }
    feedback = list(snapshot.get("feedback_records") or [])
    feedback.append(
        {
            "event_id": event_id,
            "planner_run_id": planner_run.planner_run_id,
            "recommendation_id": recommendation.recommendation_id,
            "selected_candidate_name": selected.get("name"),
            "predicted_plan_score": selected.get("plan_score"),
            "predictions": selected.get("predictions"),
            "actual_outcome": selected.get("actual_outcome"),
        }
    )
    snapshot["selected_candidate"] = selected
    snapshot["feedback_records"] = feedback[-50:]
    planner_run.input_snapshot = snapshot
    db.add(planner_run)


def _compare_recommendations(
    *,
    previous: PlannerRecommendation | None,
    current: PlannerRecommendation,
) -> PlanMetricComparison:
    current_cost = _decimal_or_zero(current.expected_cost)
    current_duration = current.expected_duration_minutes
    current_risk = current.expected_risk

    if previous is None:
        return PlanMetricComparison(
            previous_cost=None,
            new_cost=current_cost,
            cost_delta=None,
            previous_duration_minutes=None,
            new_duration_minutes=current_duration,
            duration_delta_minutes=None,
            previous_risk=None,
            new_risk=current_risk,
            risk_delta=None,
            is_improved=None,
            decision_note="No baseline recommendation available. Stored as first incident-triggered replan.",
        )

    previous_cost = _decimal_or_zero(previous.expected_cost)
    previous_duration = previous.expected_duration_minutes
    previous_risk = previous.expected_risk

    cost_delta = _money(current_cost - previous_cost)
    duration_delta = None
    if previous_duration is not None and current_duration is not None:
        duration_delta = current_duration - previous_duration

    risk_delta = None
    if previous_risk is not None and current_risk is not None:
        risk_delta = _risk_decimal(current_risk - previous_risk)

    improved = _is_replan_improved(
        previous_cost=previous_cost,
        current_cost=current_cost,
        previous_duration=previous_duration,
        current_duration=current_duration,
        previous_risk=previous_risk,
        current_risk=current_risk,
    )

    return PlanMetricComparison(
        previous_cost=previous_cost,
        new_cost=current_cost,
        cost_delta=cost_delta,
        previous_duration_minutes=previous_duration,
        new_duration_minutes=current_duration,
        duration_delta_minutes=duration_delta,
        previous_risk=previous_risk,
        new_risk=current_risk,
        risk_delta=risk_delta,
        is_improved=improved,
        decision_note=_decision_note(improved),
    )


def _apply_operator_actions_to_comparison(
    *,
    db: Session,
    event_id: str,
    comparison: PlanMetricComparison,
    operator_actions: list[dict[str, Any]],
) -> PlanMetricComparison:
    if not operator_actions:
        return comparison
    event = db.get(Event, event_id)
    if event is None:
        return comparison

    resource_delta = Decimal("0")
    timing_delta = 0
    action_notes: list[str] = []
    for action in operator_actions:
        action_type = str(action.get("action_type") or "")
        label = str(action.get("label") or "").strip()
        if action_type in {"add_resource", "swap_resource"}:
            resource_type = str(action.get("resource_type") or "")
            resource_id = str(action.get("resource_id") or "")
            resource_delta += _override_assignment_cost(
                db=db,
                event=event,
                resource_type=resource_type,
                resource_ids=[resource_id] if resource_id else [],
                fallback=Decimal("0"),
            )
            action_notes.append(label or f"{action_type.replace('_', ' ')} {resource_type}")
        elif action_type == "shift_timing":
            timing_delta += int(action.get("timing_delta_minutes") or 0)
            action_notes.append(label or "shift event timing")
        elif label:
            action_notes.append(label)

    new_cost = _money(comparison.new_cost + resource_delta)
    previous_cost = comparison.previous_cost
    cost_delta = comparison.cost_delta
    if previous_cost is not None:
        cost_delta = _money(new_cost - previous_cost)
    elif resource_delta:
        cost_delta = _money(resource_delta)

    new_duration = comparison.new_duration_minutes
    if new_duration is not None and timing_delta:
        new_duration += timing_delta
    duration_delta = comparison.duration_delta_minutes
    if comparison.previous_duration_minutes is not None and new_duration is not None:
        duration_delta = new_duration - comparison.previous_duration_minutes

    note_suffix = ""
    if action_notes:
        note_suffix = " Operator actions included: " + "; ".join(action_notes[:5]) + "."
    if resource_delta:
        note_suffix += f" Extra resource impact: {_money(resource_delta)} PLN."
    if timing_delta:
        note_suffix += f" Timing impact: {timing_delta} min."

    return PlanMetricComparison(
        previous_cost=previous_cost,
        new_cost=new_cost,
        cost_delta=cost_delta,
        previous_duration_minutes=comparison.previous_duration_minutes,
        new_duration_minutes=new_duration,
        duration_delta_minutes=duration_delta,
        previous_risk=comparison.previous_risk,
        new_risk=comparison.new_risk,
        risk_delta=comparison.risk_delta,
        is_improved=comparison.is_improved,
        decision_note=f"{comparison.decision_note}{note_suffix}",
    )


def _commit_operator_action_assignments(
    *,
    db: Session,
    event_id: str,
    planner_run_id: str,
    operator_actions: list[dict[str, Any]],
) -> None:
    event = db.get(Event, event_id)
    if event is None:
        return
    for action in operator_actions:
        if str(action.get("action_type") or "") not in {"add_resource", "swap_resource"}:
            continue
        resource_type = str(action.get("resource_type") or "")
        resource_id = str(action.get("resource_id") or "")
        if resource_type not in {"person", "equipment", "vehicle"} or not resource_id:
            continue
        assignment = Assignment(
            event_id=event_id,
            resource_type=AssignmentResourceType(resource_type),
            **_resource_fk(resource_type, resource_id),
            assignment_role=f"operator_action:{str(action.get('action_type') or '')}",
            planned_start=event.planned_start,
            planned_end=event.planned_end,
            status=AssignmentStatus.planned,
            planner_run_id=planner_run_id,
            is_manual_override=True,
            notes=(
                f"{action.get('label') or 'Operator action'} "
                f"(owner: {action.get('owner') or 'Coordinator'}, status: {action.get('status') or 'pending'})"
            ),
        )
        db.add(assignment)
    db.flush()


def _is_replan_improved(
    *,
    previous_cost: Decimal,
    current_cost: Decimal,
    previous_duration: int | None,
    current_duration: int | None,
    previous_risk: Decimal | None,
    current_risk: Decimal | None,
) -> bool:
    if previous_risk is not None and current_risk is not None and current_risk != previous_risk:
        return current_risk < previous_risk
    if current_cost != previous_cost:
        return current_cost < previous_cost
    if previous_duration is not None and current_duration is not None and current_duration != previous_duration:
        return current_duration < previous_duration
    return False


def _decision_note(is_improved: bool) -> str:
    if is_improved:
        return "New plan improves primary comparison metric(s) versus baseline."
    return "New plan does not improve baseline metrics but has been recorded for operator decision."


def _decimal_or_zero(value: Decimal | None) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return _money(value)


def _risk_decimal(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"))
