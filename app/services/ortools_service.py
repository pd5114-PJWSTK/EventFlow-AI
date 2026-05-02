from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
import importlib.util
from time import perf_counter
from typing import Literal
from uuid import uuid4


@dataclass(frozen=True)
class PlannerCandidate:
    resource_id: str
    cost_per_hour: Decimal = Decimal("0")
    score: Decimal = Decimal("0")
    available_from: datetime | None = None
    available_to: datetime | None = None


@dataclass(frozen=True)
class PlannerRequirement:
    requirement_id: str
    resource_type: str
    quantity: int = 1
    mandatory: bool = True
    required_start: datetime | None = None
    required_end: datetime | None = None
    candidates: list[PlannerCandidate] = field(default_factory=list)


@dataclass(frozen=True)
class PlannerInput:
    requirements: list[PlannerRequirement] = field(default_factory=list)


@dataclass(frozen=True)
class PlannerPolicy:
    timeout_seconds: float = 10.0
    fallback_enabled: bool = True

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise PlannerPolicyError("timeout_seconds must be greater than 0")


@dataclass(frozen=True)
class PlannerAssignment:
    requirement_id: str
    resource_ids: list[str]
    unassigned_count: int
    estimated_cost: Decimal


@dataclass(frozen=True)
class PlannerResult:
    plan_id: str
    solver: Literal["ortools", "fallback"]
    assignments: list[PlannerAssignment]
    estimated_cost: Decimal
    duration_ms: int = 0
    fallback_reason: str | None = None


class PlannerPolicyError(ValueError):
    pass


class PlannerTimeoutError(TimeoutError):
    pass


class PlannerService:
    def __init__(self, policy: PlannerPolicy | None = None) -> None:
        self.policy = policy or PlannerPolicy()

    def solve(self, model: PlannerInput) -> PlannerResult:
        started_at = perf_counter()
        deadline = started_at + self.policy.timeout_seconds
        fallback_reason: str | None = None

        try:
            ortools_result = self._try_ortools(model, deadline=deadline)
            if ortools_result is not None:
                return _with_duration(ortools_result, started_at)
            fallback_reason = "ortools_unavailable"
        except PlannerTimeoutError:
            fallback_reason = "ortools_timeout"

        if not self.policy.fallback_enabled:
            raise PlannerPolicyError(f"Fallback disabled after {fallback_reason}")

        fallback_result = self._fallback_greedy(
            model,
            solver_name="fallback",
            deadline=deadline,
            fallback_reason=fallback_reason,
        )
        return _with_duration(fallback_result, started_at)

    def _try_ortools(
        self, model: PlannerInput, *, deadline: float
    ) -> PlannerResult | None:
        try:
            has_ortools = (
                importlib.util.find_spec("ortools.constraint_solver") is not None
            )
        except ModuleNotFoundError:
            has_ortools = False

        if not has_ortools:
            return None

        # Scaffold: until the real model is implemented, reuse the fallback logic.
        return self._fallback_greedy(
            model,
            solver_name="ortools",
            deadline=deadline,
            fallback_reason=None,
        )

    def _fallback_greedy(
        self,
        model: PlannerInput,
        *,
        solver_name: Literal["ortools", "fallback"],
        deadline: float,
        fallback_reason: str | None,
    ) -> PlannerResult:
        assignments: list[PlannerAssignment] = []
        schedule: dict[str, list[tuple[datetime | None, datetime | None]]] = {}
        total_cost = Decimal("0")

        for requirement in model.requirements:
            _raise_if_timed_out(deadline)
            requirement_hours = _requirement_hours(requirement)
            selected_ids: list[str] = []
            selected_cost = Decimal("0")

            for candidate in _sorted_candidates(requirement.candidates):
                _raise_if_timed_out(deadline)
                if not _candidate_covers_window(candidate, requirement):
                    continue
                if not _can_use_resource(schedule, candidate.resource_id, requirement):
                    continue

                selected_ids.append(candidate.resource_id)
                _record_assignment(schedule, candidate.resource_id, requirement)

                selected_cost += candidate.cost_per_hour * requirement_hours
                if len(selected_ids) >= requirement.quantity:
                    break

            unassigned = max(requirement.quantity - len(selected_ids), 0)
            assignment = PlannerAssignment(
                requirement_id=requirement.requirement_id,
                resource_ids=selected_ids,
                unassigned_count=unassigned,
                estimated_cost=selected_cost,
            )
            assignments.append(assignment)
            total_cost += selected_cost

        return PlannerResult(
            plan_id=str(uuid4()),
            solver=solver_name,
            assignments=assignments,
            estimated_cost=total_cost,
            fallback_reason=fallback_reason,
        )


def _sorted_candidates(candidates: list[PlannerCandidate]) -> list[PlannerCandidate]:
    return sorted(
        candidates,
        key=lambda candidate: (
            -candidate.score,
            candidate.cost_per_hour,
            candidate.resource_id,
        ),
    )


def _requirement_hours(requirement: PlannerRequirement) -> Decimal:
    if requirement.required_start and requirement.required_end:
        duration = (
            requirement.required_end - requirement.required_start
        ).total_seconds()
        if duration <= 0:
            return Decimal("0")
        return Decimal(str(duration / 3600.0))
    return Decimal("1")


def _candidate_covers_window(
    candidate: PlannerCandidate, requirement: PlannerRequirement
) -> bool:
    if not requirement.required_start or not requirement.required_end:
        return True
    if candidate.available_from is None or candidate.available_to is None:
        return True
    return (
        candidate.available_from <= requirement.required_start
        and candidate.available_to >= requirement.required_end
    )


def _can_use_resource(
    schedule: dict[str, list[tuple[datetime | None, datetime | None]]],
    resource_id: str,
    requirement: PlannerRequirement,
) -> bool:
    windows = schedule.get(resource_id, [])
    if not windows:
        return True

    req_start = requirement.required_start
    req_end = requirement.required_end
    if req_start is None or req_end is None:
        return False

    for start, end in windows:
        if start is None or end is None:
            return False
        if _windows_overlap(req_start, req_end, start, end):
            return False

    return True


def _record_assignment(
    schedule: dict[str, list[tuple[datetime | None, datetime | None]]],
    resource_id: str,
    requirement: PlannerRequirement,
) -> None:
    schedule.setdefault(resource_id, []).append(
        (requirement.required_start, requirement.required_end)
    )


def _windows_overlap(
    start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime
) -> bool:
    latest_start = max(start_a, start_b)
    earliest_end = min(end_a, end_b)
    return latest_start < earliest_end


def _raise_if_timed_out(deadline: float) -> None:
    if perf_counter() > deadline:
        raise PlannerTimeoutError("Planner timeout exceeded")


def _with_duration(result: PlannerResult, started_at: float) -> PlannerResult:
    return PlannerResult(
        plan_id=result.plan_id,
        solver=result.solver,
        assignments=result.assignments,
        estimated_cost=result.estimated_cost,
        duration_ms=max(int((perf_counter() - started_at) * 1000), 0),
        fallback_reason=result.fallback_reason,
    )
