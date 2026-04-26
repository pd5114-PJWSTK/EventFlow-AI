from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.core import (
    Equipment,
    EquipmentAvailability,
    PeopleAvailability,
    ResourcePerson,
    Vehicle,
    VehicleAvailability,
)
from app.schemas.availability import AvailabilityCreate, AvailabilityUpdate


class AvailabilityValidationError(ValueError):
    pass


def _validate_time_range(start: datetime, end: datetime) -> None:
    if end <= start:
        raise AvailabilityValidationError("available_to must be after available_from")


def _check_overlap(
    db: Session,
    model: type[PeopleAvailability] | type[EquipmentAvailability] | type[VehicleAvailability],
    fk_field: str,
    fk_value: str,
    start: datetime,
    end: datetime,
    exclude_id: str | None = None,
) -> None:
    query = select(func.count()).select_from(model).where(
        getattr(model, fk_field) == fk_value,
        model.available_from < end,
        model.available_to > start,
    )
    if exclude_id is not None:
        query = query.where(model.availability_id != exclude_id)
    exists = (db.scalar(query) or 0) > 0
    if exists:
        raise AvailabilityValidationError("availability window overlaps an existing window")


def _person_exists(db: Session, person_id: str) -> None:
    if db.get(ResourcePerson, person_id) is None:
        raise AvailabilityValidationError("person_id does not exist")


def _equipment_exists(db: Session, equipment_id: str) -> None:
    if db.get(Equipment, equipment_id) is None:
        raise AvailabilityValidationError("equipment_id does not exist")


def _vehicle_exists(db: Session, vehicle_id: str) -> None:
    if db.get(Vehicle, vehicle_id) is None:
        raise AvailabilityValidationError("vehicle_id does not exist")


def create_people_availability(db: Session, person_id: str, payload: AvailabilityCreate) -> PeopleAvailability:
    _person_exists(db, person_id)
    _validate_time_range(payload.available_from, payload.available_to)
    _check_overlap(db, PeopleAvailability, "person_id", person_id, payload.available_from, payload.available_to)

    item = PeopleAvailability(person_id=person_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_people_availability(db: Session, person_id: str, limit: int, offset: int) -> tuple[list[PeopleAvailability], int]:
    _person_exists(db, person_id)
    items = (
        db.execute(
            select(PeopleAvailability)
            .where(PeopleAvailability.person_id == person_id)
            .order_by(PeopleAvailability.available_from.asc())
            .offset(offset)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    total = (
        db.scalar(
            select(func.count())
            .select_from(PeopleAvailability)
            .where(PeopleAvailability.person_id == person_id)
        )
        or 0
    )
    return items, int(total)


def get_people_availability(db: Session, person_id: str, availability_id: str) -> PeopleAvailability | None:
    item = db.get(PeopleAvailability, availability_id)
    if item is None or item.person_id != person_id:
        return None
    return item


def update_people_availability(
    db: Session,
    item: PeopleAvailability,
    payload: AvailabilityUpdate,
) -> PeopleAvailability:
    patch = payload.model_dump(exclude_unset=True)
    start = patch.get("available_from", item.available_from)
    end = patch.get("available_to", item.available_to)
    _validate_time_range(start, end)
    _check_overlap(db, PeopleAvailability, "person_id", item.person_id, start, end, exclude_id=item.availability_id)

    for key, value in patch.items():
        setattr(item, key, value)

    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def delete_people_availability(db: Session, item: PeopleAvailability) -> None:
    db.delete(item)
    db.commit()


def create_equipment_availability(db: Session, equipment_id: str, payload: AvailabilityCreate) -> EquipmentAvailability:
    _equipment_exists(db, equipment_id)
    _validate_time_range(payload.available_from, payload.available_to)
    _check_overlap(db, EquipmentAvailability, "equipment_id", equipment_id, payload.available_from, payload.available_to)

    item = EquipmentAvailability(equipment_id=equipment_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_equipment_availability(
    db: Session,
    equipment_id: str,
    limit: int,
    offset: int,
) -> tuple[list[EquipmentAvailability], int]:
    _equipment_exists(db, equipment_id)
    items = (
        db.execute(
            select(EquipmentAvailability)
            .where(EquipmentAvailability.equipment_id == equipment_id)
            .order_by(EquipmentAvailability.available_from.asc())
            .offset(offset)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    total = (
        db.scalar(
            select(func.count())
            .select_from(EquipmentAvailability)
            .where(EquipmentAvailability.equipment_id == equipment_id)
        )
        or 0
    )
    return items, int(total)


def get_equipment_availability(
    db: Session,
    equipment_id: str,
    availability_id: str,
) -> EquipmentAvailability | None:
    item = db.get(EquipmentAvailability, availability_id)
    if item is None or item.equipment_id != equipment_id:
        return None
    return item


def update_equipment_availability(
    db: Session,
    item: EquipmentAvailability,
    payload: AvailabilityUpdate,
) -> EquipmentAvailability:
    patch = payload.model_dump(exclude_unset=True)
    start = patch.get("available_from", item.available_from)
    end = patch.get("available_to", item.available_to)
    _validate_time_range(start, end)
    _check_overlap(
        db,
        EquipmentAvailability,
        "equipment_id",
        item.equipment_id,
        start,
        end,
        exclude_id=item.availability_id,
    )

    for key, value in patch.items():
        setattr(item, key, value)

    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def delete_equipment_availability(db: Session, item: EquipmentAvailability) -> None:
    db.delete(item)
    db.commit()


def create_vehicle_availability(db: Session, vehicle_id: str, payload: AvailabilityCreate) -> VehicleAvailability:
    _vehicle_exists(db, vehicle_id)
    _validate_time_range(payload.available_from, payload.available_to)
    _check_overlap(db, VehicleAvailability, "vehicle_id", vehicle_id, payload.available_from, payload.available_to)

    item = VehicleAvailability(vehicle_id=vehicle_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_vehicle_availability(db: Session, vehicle_id: str, limit: int, offset: int) -> tuple[list[VehicleAvailability], int]:
    _vehicle_exists(db, vehicle_id)
    items = (
        db.execute(
            select(VehicleAvailability)
            .where(VehicleAvailability.vehicle_id == vehicle_id)
            .order_by(VehicleAvailability.available_from.asc())
            .offset(offset)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    total = (
        db.scalar(
            select(func.count())
            .select_from(VehicleAvailability)
            .where(VehicleAvailability.vehicle_id == vehicle_id)
        )
        or 0
    )
    return items, int(total)


def get_vehicle_availability(db: Session, vehicle_id: str, availability_id: str) -> VehicleAvailability | None:
    item = db.get(VehicleAvailability, availability_id)
    if item is None or item.vehicle_id != vehicle_id:
        return None
    return item


def update_vehicle_availability(
    db: Session,
    item: VehicleAvailability,
    payload: AvailabilityUpdate,
) -> VehicleAvailability:
    patch = payload.model_dump(exclude_unset=True)
    start = patch.get("available_from", item.available_from)
    end = patch.get("available_to", item.available_to)
    _validate_time_range(start, end)
    _check_overlap(db, VehicleAvailability, "vehicle_id", item.vehicle_id, start, end, exclude_id=item.availability_id)

    for key, value in patch.items():
        setattr(item, key, value)

    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def delete_vehicle_availability(db: Session, item: VehicleAvailability) -> None:
    db.delete(item)
    db.commit()
