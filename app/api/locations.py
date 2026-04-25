from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.locations import LocationCreate, LocationListResponse, LocationRead, LocationUpdate
from app.services.location_service import (
    create_location,
    delete_location,
    get_location,
    list_locations,
    update_location,
)


router = APIRouter(prefix="/api/locations", tags=["locations"])


@router.post("", response_model=LocationRead, status_code=status.HTTP_201_CREATED)
def create_location_endpoint(payload: LocationCreate, db: Session = Depends(get_db)) -> LocationRead:
    return create_location(db, payload)


@router.get("", response_model=LocationListResponse)
def list_locations_endpoint(
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> LocationListResponse:
    items, total = list_locations(db, limit=limit, offset=offset)
    return LocationListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{location_id}", response_model=LocationRead)
def get_location_endpoint(location_id: str, db: Session = Depends(get_db)) -> LocationRead:
    location = get_location(db, location_id)
    if location is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return location


@router.patch("/{location_id}", response_model=LocationRead)
def update_location_endpoint(location_id: str, payload: LocationUpdate, db: Session = Depends(get_db)) -> LocationRead:
    location = get_location(db, location_id)
    if location is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return update_location(db, location, payload)


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_location_endpoint(location_id: str, db: Session = Depends(get_db)) -> Response:
    location = get_location(db, location_id)
    if location is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    delete_location(db, location)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
