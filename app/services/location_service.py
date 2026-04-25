from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.core import Location
from app.schemas.locations import LocationCreate, LocationUpdate


def create_location(db: Session, payload: LocationCreate) -> Location:
    location = Location(**payload.model_dump())
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


def get_location(db: Session, location_id: str) -> Location | None:
    return db.get(Location, location_id)


def list_locations(db: Session, limit: int, offset: int) -> tuple[list[Location], int]:
    items = (
        db.execute(
            select(Location)
            .order_by(Location.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    total = db.scalar(select(func.count()).select_from(Location)) or 0
    return items, int(total)


def update_location(db: Session, location: Location, payload: LocationUpdate) -> Location:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(location, key, value)
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


def delete_location(db: Session, location: Location) -> None:
    db.delete(location)
    db.commit()
