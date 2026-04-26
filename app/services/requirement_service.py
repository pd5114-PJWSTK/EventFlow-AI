from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.core import EquipmentType, Event, EventRequirement, RequirementType, Skill, VehicleType
from app.schemas.requirements import EventRequirementCreate, EventRequirementUpdate


class RequirementValidationError(ValueError):
    pass


def _event_exists(db: Session, event_id: str) -> None:
    if db.get(Event, event_id) is None:
        raise RequirementValidationError("event_id does not exist")


def _skill_exists(db: Session, skill_id: str | None) -> None:
    if skill_id is None:
        return
    if db.get(Skill, skill_id) is None:
        raise RequirementValidationError("skill_id does not exist")


def _equipment_type_exists(db: Session, equipment_type_id: str | None) -> None:
    if equipment_type_id is None:
        return
    if db.get(EquipmentType, equipment_type_id) is None:
        raise RequirementValidationError("equipment_type_id does not exist")


def _validate_requirement_fields(
    requirement_type: RequirementType,
    role_required: str | None,
    skill_id: str | None,
    equipment_type_id: str | None,
    vehicle_type_required: VehicleType | None,
) -> None:
    if requirement_type == RequirementType.person_role and role_required is None:
        raise RequirementValidationError("role_required is required for person_role")
    if requirement_type == RequirementType.person_skill and skill_id is None:
        raise RequirementValidationError("skill_id is required for person_skill")
    if requirement_type == RequirementType.equipment_type and equipment_type_id is None:
        raise RequirementValidationError("equipment_type_id is required for equipment_type")
    if requirement_type == RequirementType.vehicle_type and vehicle_type_required is None:
        raise RequirementValidationError("vehicle_type_required is required for vehicle_type")


def _validate_time_range(start: datetime | None, end: datetime | None) -> None:
    if start is not None and end is not None and end <= start:
        raise RequirementValidationError("required_end must be after required_start")


def create_requirement(db: Session, event_id: str, payload: EventRequirementCreate) -> EventRequirement:
    _event_exists(db, event_id)
    _skill_exists(db, payload.skill_id)
    _equipment_type_exists(db, payload.equipment_type_id)
    _validate_requirement_fields(
        payload.requirement_type,
        payload.role_required.value if payload.role_required else None,
        payload.skill_id,
        payload.equipment_type_id,
        payload.vehicle_type_required,
    )
    _validate_time_range(payload.required_start, payload.required_end)

    requirement = EventRequirement(event_id=event_id, **payload.model_dump())
    db.add(requirement)
    db.commit()
    db.refresh(requirement)
    return requirement


def get_requirement(db: Session, event_id: str, requirement_id: str) -> EventRequirement | None:
    requirement = db.get(EventRequirement, requirement_id)
    if requirement is None or requirement.event_id != event_id:
        return None
    return requirement


def list_requirements(db: Session, event_id: str, limit: int, offset: int) -> tuple[list[EventRequirement], int]:
    _event_exists(db, event_id)
    items = (
        db.execute(
            select(EventRequirement)
            .where(EventRequirement.event_id == event_id)
            .order_by(EventRequirement.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    total = (
        db.scalar(
            select(func.count())
            .select_from(EventRequirement)
            .where(EventRequirement.event_id == event_id)
        )
        or 0
    )
    return items, int(total)


def update_requirement(db: Session, requirement: EventRequirement, payload: EventRequirementUpdate) -> EventRequirement:
    patch = payload.model_dump(exclude_unset=True)

    req_type = patch.get("requirement_type", requirement.requirement_type)
    role_required = patch.get("role_required", requirement.role_required)
    skill_id = patch.get("skill_id", requirement.skill_id)
    equipment_type_id = patch.get("equipment_type_id", requirement.equipment_type_id)
    vehicle_type_required = patch.get("vehicle_type_required", requirement.vehicle_type_required)
    required_start = patch.get("required_start", requirement.required_start)
    required_end = patch.get("required_end", requirement.required_end)

    _skill_exists(db, skill_id)
    _equipment_type_exists(db, equipment_type_id)
    _validate_requirement_fields(
        req_type,
        role_required.value if role_required else None,
        skill_id,
        equipment_type_id,
        vehicle_type_required,
    )
    _validate_time_range(required_start, required_end)

    for key, value in patch.items():
        setattr(requirement, key, value)

    db.add(requirement)
    db.commit()
    db.refresh(requirement)
    return requirement


def delete_requirement(db: Session, requirement: EventRequirement) -> None:
    db.delete(requirement)
    db.commit()
