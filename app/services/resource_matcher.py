from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.models.core import (
    Equipment,
    Event,
    EventRequirement,
    RequirementType,
    ResourcePerson,
    Vehicle,
)


@dataclass
class RankedResource:
    resource_id: str
    resource_type: str
    score: Decimal
    estimated_cost: Decimal


def _score_from_cost(cost: Decimal | None) -> Decimal:
    if cost is None:
        return Decimal("0")
    return Decimal("1") / (cost + Decimal("1"))


def _person_reliability_score(person: ResourcePerson) -> Decimal:
    if person.reliability_notes:
        text = person.reliability_notes.lower()
        if "high" in text:
            return Decimal("0.20")
        if "medium" in text:
            return Decimal("0.10")
    return Decimal("0")


def rank_people_for_requirement(
    requirement: EventRequirement,
    people: list[ResourcePerson],
) -> list[RankedResource]:
    ranked: list[RankedResource] = []
    for person in people:
        if (
            requirement.requirement_type == RequirementType.person_role
            and requirement.role_required is not None
        ):
            if person.role != requirement.role_required:
                continue

        base_cost = person.cost_per_hour or Decimal("0")
        score = _score_from_cost(base_cost) + _person_reliability_score(person)
        ranked.append(
            RankedResource(
                resource_id=person.person_id,
                resource_type="person",
                score=score,
                estimated_cost=base_cost,
            )
        )

    ranked.sort(key=lambda item: (item.score, -item.estimated_cost), reverse=True)
    return ranked


def rank_equipment_for_requirement(
    requirement: EventRequirement,
    equipment: list[Equipment],
) -> list[RankedResource]:
    ranked: list[RankedResource] = []
    for item in equipment:
        if (
            requirement.requirement_type == RequirementType.equipment_type
            and requirement.equipment_type_id is not None
        ):
            if item.equipment_type_id != requirement.equipment_type_id:
                continue

        base_cost = item.hourly_cost_estimate or Decimal("0")
        ranked.append(
            RankedResource(
                resource_id=item.equipment_id,
                resource_type="equipment",
                score=_score_from_cost(base_cost),
                estimated_cost=base_cost,
            )
        )

    ranked.sort(key=lambda entry: (entry.score, -entry.estimated_cost), reverse=True)
    return ranked


def rank_vehicles_for_requirement(
    requirement: EventRequirement,
    vehicles: list[Vehicle],
) -> list[RankedResource]:
    ranked: list[RankedResource] = []
    for vehicle in vehicles:
        if (
            requirement.requirement_type == RequirementType.vehicle_type
            and requirement.vehicle_type_required is not None
        ):
            if vehicle.vehicle_type != requirement.vehicle_type_required:
                continue

        base_cost = vehicle.cost_per_hour or Decimal("0")
        ranked.append(
            RankedResource(
                resource_id=vehicle.vehicle_id,
                resource_type="vehicle",
                score=_score_from_cost(base_cost),
                estimated_cost=base_cost,
            )
        )

    ranked.sort(key=lambda entry: (entry.score, -entry.estimated_cost), reverse=True)
    return ranked


def match_event_requirements(
    event: Event,
    requirements: list[EventRequirement],
    people: list[ResourcePerson],
    equipment: list[Equipment],
    vehicles: list[Vehicle],
) -> dict[str, list[RankedResource]]:
    del event  # Reserved for future extensions with event-level weighting.

    matches: dict[str, list[RankedResource]] = {}
    for requirement in requirements:
        if requirement.requirement_type in (
            RequirementType.person_role,
            RequirementType.person_skill,
        ):
            matches[requirement.requirement_id] = rank_people_for_requirement(
                requirement, people
            )
        elif requirement.requirement_type == RequirementType.equipment_type:
            matches[requirement.requirement_id] = rank_equipment_for_requirement(
                requirement, equipment
            )
        elif requirement.requirement_type == RequirementType.vehicle_type:
            matches[requirement.requirement_id] = rank_vehicles_for_requirement(
                requirement, vehicles
            )
        else:
            matches[requirement.requirement_id] = []
    return matches
