from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import importlib.util

from app.services.ortools_service import (
    PlannerCandidate,
    PlannerInput,
    PlannerPolicy,
    PlannerPolicyError,
    PlannerTimeoutError,
    PlannerRequirement,
    PlannerService,
)


def test_fallback_used_when_ortools_missing(monkeypatch) -> None:
    original_find_spec = importlib.util.find_spec

    def fake_find_spec(name: str, package: str | None = None):
        if name == "ortools.constraint_solver":
            return None
        return original_find_spec(name, package)

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)

    requirement = PlannerRequirement(
        requirement_id="req-1",
        resource_type="person",
        quantity=1,
        required_start=datetime(2030, 1, 1, 8, 0, 0),
        required_end=datetime(2030, 1, 1, 10, 0, 0),
        candidates=[
            PlannerCandidate(
                resource_id="person-1",
                cost_per_hour=Decimal("50"),
                score=Decimal("0.50"),
            ),
            PlannerCandidate(
                resource_id="person-2",
                cost_per_hour=Decimal("40"),
                score=Decimal("0.70"),
            ),
        ],
    )

    result = PlannerService().solve(PlannerInput(requirements=[requirement]))

    assert result.solver == "fallback"
    assert result.assignments[0].resource_ids == ["person-2"]
    assert result.assignments[0].estimated_cost == Decimal("80")
    assert result.estimated_cost == Decimal("80")


def test_fallback_respects_availability_and_quantity(monkeypatch) -> None:
    original_find_spec = importlib.util.find_spec

    def fake_find_spec(name: str, package: str | None = None):
        if name == "ortools.constraint_solver":
            return None
        return original_find_spec(name, package)

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)

    requirement = PlannerRequirement(
        requirement_id="req-2",
        resource_type="person",
        quantity=2,
        required_start=datetime(2030, 1, 1, 9, 0, 0),
        required_end=datetime(2030, 1, 1, 12, 0, 0),
        candidates=[
            PlannerCandidate(
                resource_id="person-unavailable",
                cost_per_hour=Decimal("60"),
                score=Decimal("0.95"),
                available_from=datetime(2030, 1, 1, 12, 0, 0),
                available_to=datetime(2030, 1, 1, 13, 0, 0),
            ),
            PlannerCandidate(
                resource_id="person-1",
                cost_per_hour=Decimal("100"),
                score=Decimal("0.90"),
                available_from=datetime(2030, 1, 1, 8, 0, 0),
                available_to=datetime(2030, 1, 1, 13, 0, 0),
            ),
            PlannerCandidate(
                resource_id="person-2",
                cost_per_hour=Decimal("80"),
                score=Decimal("0.85"),
                available_from=datetime(2030, 1, 1, 8, 0, 0),
                available_to=datetime(2030, 1, 1, 13, 0, 0),
            ),
        ],
    )

    result = PlannerService().solve(PlannerInput(requirements=[requirement]))

    assert result.solver == "fallback"
    assert result.assignments[0].resource_ids == ["person-1", "person-2"]
    assert result.assignments[0].unassigned_count == 0
    assert result.assignments[0].estimated_cost == Decimal("540")
    assert result.estimated_cost == Decimal("540")


def test_fallback_policy_can_be_disabled(monkeypatch) -> None:
    original_find_spec = importlib.util.find_spec

    def fake_find_spec(name: str, package: str | None = None):
        if name == "ortools.constraint_solver":
            return None
        return original_find_spec(name, package)

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)

    service = PlannerService(
        policy=PlannerPolicy(timeout_seconds=1.0, fallback_enabled=False)
    )

    try:
        service.solve(PlannerInput())
    except PlannerPolicyError as exc:
        assert "Fallback disabled" in str(exc)
    else:
        raise AssertionError("Expected fallback-disabled policy error")


def test_large_fallback_plan_completes_under_target(monkeypatch) -> None:
    original_find_spec = importlib.util.find_spec

    def fake_find_spec(name: str, package: str | None = None):
        if name == "ortools.constraint_solver":
            return None
        return original_find_spec(name, package)

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)

    requirements = [
        PlannerRequirement(
            requirement_id=f"req-{index}",
            resource_type="person",
            quantity=1,
            required_start=datetime(2030, 1, 1, 8, 0, 0),
            required_end=datetime(2030, 1, 1, 9, 0, 0),
            candidates=[
                PlannerCandidate(
                    resource_id=f"person-{index}-{candidate}",
                    cost_per_hour=Decimal(candidate + 1),
                    score=Decimal("1") / Decimal(candidate + 1),
                    available_from=datetime(2030, 1, 1, 7, 0, 0),
                    available_to=datetime(2030, 1, 1, 10, 0, 0),
                )
                for candidate in range(3)
            ],
        )
        for index in range(120)
    ]

    result = PlannerService(
        policy=PlannerPolicy(timeout_seconds=10.0, fallback_enabled=True)
    ).solve(PlannerInput(requirements=requirements))

    assert result.solver == "fallback"
    assert result.fallback_reason == "ortools_unavailable"
    assert len(result.assignments) == 120
    assert sum(item.unassigned_count for item in result.assignments) == 0
    assert result.duration_ms < 10_000


def test_fallback_respects_timeout(monkeypatch) -> None:
    original_find_spec = importlib.util.find_spec

    def fake_find_spec(name: str, package: str | None = None):
        if name == "ortools.constraint_solver":
            return None
        return original_find_spec(name, package)

    calls = iter([100.0, 101.0])

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)
    monkeypatch.setattr(
        "app.services.ortools_service.perf_counter", lambda: next(calls)
    )

    requirement = PlannerRequirement(
        requirement_id="req-timeout",
        resource_type="person",
        candidates=[PlannerCandidate(resource_id="person-1")],
    )
    service = PlannerService(
        policy=PlannerPolicy(timeout_seconds=0.5, fallback_enabled=True)
    )

    try:
        service.solve(PlannerInput(requirements=[requirement]))
    except PlannerTimeoutError as exc:
        assert "timeout" in str(exc).lower()
    else:
        raise AssertionError("Expected planner timeout")
