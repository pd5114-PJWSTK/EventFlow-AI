from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.core import Equipment, EquipmentType, Location, PersonSkill, ResourcePerson, Skill, Vehicle
from app.schemas.resources import (
    EquipmentCreate,
    EquipmentTypeCreate,
    EquipmentUpdate,
    PersonCreate,
    PersonSkillAssign,
    PersonUpdate,
    SkillCreate,
    VehicleCreate,
    VehicleUpdate,
)


class ResourceValidationError(ValueError):
    pass


def _location_exists(db: Session, location_id: str | None) -> None:
    if location_id is None:
        return
    if db.get(Location, location_id) is None:
        raise ResourceValidationError("location_id does not exist")


def _skill_exists(db: Session, skill_id: str) -> None:
    if db.get(Skill, skill_id) is None:
        raise ResourceValidationError("skill_id does not exist")


def _equipment_type_exists(db: Session, equipment_type_id: str) -> None:
    if db.get(EquipmentType, equipment_type_id) is None:
        raise ResourceValidationError("equipment_type_id does not exist")


def create_skill(db: Session, payload: SkillCreate) -> Skill:
    skill = Skill(**payload.model_dump())
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return skill


def get_skill(db: Session, skill_id: str) -> Skill | None:
    return db.get(Skill, skill_id)


def list_skills(db: Session, limit: int, offset: int) -> tuple[list[Skill], int]:
    items = db.execute(select(Skill).order_by(Skill.skill_name.asc()).offset(offset).limit(limit)).scalars().all()
    total = db.scalar(select(func.count()).select_from(Skill)) or 0
    return items, int(total)


def create_person(db: Session, payload: PersonCreate) -> ResourcePerson:
    data = payload.model_dump()
    _location_exists(db, data.get("home_base_location_id"))
    person = ResourcePerson(**data)
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


def get_person(db: Session, person_id: str) -> ResourcePerson | None:
    return db.get(ResourcePerson, person_id)


def list_people(db: Session, limit: int, offset: int) -> tuple[list[ResourcePerson], int]:
    items = (
        db.execute(select(ResourcePerson).order_by(ResourcePerson.created_at.desc()).offset(offset).limit(limit))
        .scalars()
        .all()
    )
    total = db.scalar(select(func.count()).select_from(ResourcePerson)) or 0
    return items, int(total)


def update_person(db: Session, person: ResourcePerson, payload: PersonUpdate) -> ResourcePerson:
    patch = payload.model_dump(exclude_unset=True)
    if "home_base_location_id" in patch:
        _location_exists(db, patch["home_base_location_id"])
    for key, value in patch.items():
        setattr(person, key, value)
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


def delete_person(db: Session, person: ResourcePerson) -> None:
    db.delete(person)
    db.commit()


def assign_skill_to_person(db: Session, person: ResourcePerson, payload: PersonSkillAssign) -> PersonSkill:
    _skill_exists(db, payload.skill_id)
    link = db.get(PersonSkill, {"person_id": person.person_id, "skill_id": payload.skill_id})
    if link is None:
        link = PersonSkill(person_id=person.person_id, skill_id=payload.skill_id, skill_level=payload.skill_level)
    link.skill_level = payload.skill_level
    link.certified = payload.certified
    link.notes = payload.notes
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def create_equipment_type(db: Session, payload: EquipmentTypeCreate) -> EquipmentType:
    item = EquipmentType(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_equipment_type(db: Session, equipment_type_id: str) -> EquipmentType | None:
    return db.get(EquipmentType, equipment_type_id)


def list_equipment_types(db: Session, limit: int, offset: int) -> tuple[list[EquipmentType], int]:
    items = (
        db.execute(select(EquipmentType).order_by(EquipmentType.type_name.asc()).offset(offset).limit(limit))
        .scalars()
        .all()
    )
    total = db.scalar(select(func.count()).select_from(EquipmentType)) or 0
    return items, int(total)


def create_equipment(db: Session, payload: EquipmentCreate) -> Equipment:
    data = payload.model_dump()
    _equipment_type_exists(db, data["equipment_type_id"])
    _location_exists(db, data.get("warehouse_location_id"))
    equipment = Equipment(**data)
    db.add(equipment)
    db.commit()
    db.refresh(equipment)
    return equipment


def get_equipment(db: Session, equipment_id: str) -> Equipment | None:
    return db.get(Equipment, equipment_id)


def list_equipment(db: Session, limit: int, offset: int) -> tuple[list[Equipment], int]:
    items = db.execute(select(Equipment).order_by(Equipment.created_at.desc()).offset(offset).limit(limit)).scalars().all()
    total = db.scalar(select(func.count()).select_from(Equipment)) or 0
    return items, int(total)


def update_equipment(db: Session, equipment: Equipment, payload: EquipmentUpdate) -> Equipment:
    patch = payload.model_dump(exclude_unset=True)
    if "equipment_type_id" in patch and patch["equipment_type_id"] is not None:
        _equipment_type_exists(db, patch["equipment_type_id"])
    if "warehouse_location_id" in patch:
        _location_exists(db, patch["warehouse_location_id"])
    for key, value in patch.items():
        setattr(equipment, key, value)
    db.add(equipment)
    db.commit()
    db.refresh(equipment)
    return equipment


def delete_equipment(db: Session, equipment: Equipment) -> None:
    db.delete(equipment)
    db.commit()


def create_vehicle(db: Session, payload: VehicleCreate) -> Vehicle:
    data = payload.model_dump()
    _location_exists(db, data.get("home_location_id"))
    vehicle = Vehicle(**data)
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


def get_vehicle(db: Session, vehicle_id: str) -> Vehicle | None:
    return db.get(Vehicle, vehicle_id)


def list_vehicles(db: Session, limit: int, offset: int) -> tuple[list[Vehicle], int]:
    items = db.execute(select(Vehicle).order_by(Vehicle.created_at.desc()).offset(offset).limit(limit)).scalars().all()
    total = db.scalar(select(func.count()).select_from(Vehicle)) or 0
    return items, int(total)


def update_vehicle(db: Session, vehicle: Vehicle, payload: VehicleUpdate) -> Vehicle:
    patch = payload.model_dump(exclude_unset=True)
    if "home_location_id" in patch:
        _location_exists(db, patch["home_location_id"])
    for key, value in patch.items():
        setattr(vehicle, key, value)
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


def delete_vehicle(db: Session, vehicle: Vehicle) -> None:
    db.delete(vehicle)
    db.commit()
