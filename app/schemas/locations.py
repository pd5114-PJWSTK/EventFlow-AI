from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.core import LocationType


def _validate_city_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        raise ValueError("city must not be empty")
    if not any(char.isalpha() for char in stripped):
        raise ValueError("city must contain letters")
    allowed = set(" .'-")
    if any(not (char.isalpha() or char in allowed) for char in stripped):
        raise ValueError("city can contain only letters, spaces, apostrophe, dot and hyphen")
    return stripped


class LocationCreate(BaseModel):
    name: str | None = None
    city: str = Field(min_length=1, max_length=255)
    address_line: str | None = None
    postal_code: str | None = None
    country_code: str = Field(default="PL", min_length=2, max_length=2)
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    location_type: LocationType = LocationType.other
    parking_difficulty: int = Field(default=1, ge=1, le=5)
    access_difficulty: int = Field(default=1, ge=1, le=5)
    setup_complexity_score: int = Field(default=1, ge=1, le=10)
    notes: str | None = None

    @field_validator("city")
    @classmethod
    def validate_city(cls, value: str) -> str:
        result = _validate_city_text(value)
        if result is None:
            raise ValueError("city must not be empty")
        return result


class LocationUpdate(BaseModel):
    name: str | None = None
    city: str | None = Field(default=None, min_length=1, max_length=255)
    address_line: str | None = None
    postal_code: str | None = None
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    location_type: LocationType | None = None
    parking_difficulty: int | None = Field(default=None, ge=1, le=5)
    access_difficulty: int | None = Field(default=None, ge=1, le=5)
    setup_complexity_score: int | None = Field(default=None, ge=1, le=10)
    notes: str | None = None

    @field_validator("city")
    @classmethod
    def validate_city(cls, value: str | None) -> str | None:
        return _validate_city_text(value)


class LocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    location_id: str
    name: str | None
    city: str
    address_line: str | None
    postal_code: str | None
    country_code: str
    latitude: Decimal | None
    longitude: Decimal | None
    location_type: LocationType
    parking_difficulty: int
    access_difficulty: int
    setup_complexity_score: int
    notes: str | None
    created_at: datetime


class LocationListResponse(BaseModel):
    items: list[LocationRead]
    total: int
    limit: int
    offset: int
