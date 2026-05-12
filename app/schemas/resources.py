from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.core import EmploymentType, PersonRole, ResourceStatus, VehicleType


class SkillCreate(BaseModel):
    skill_name: str = Field(min_length=1, max_length=120)
    skill_category: str | None = None
    description: str | None = None


class SkillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    skill_id: str
    skill_name: str
    skill_category: str | None
    description: str | None


class SkillListResponse(BaseModel):
    items: list[SkillRead]
    total: int
    limit: int
    offset: int


class PersonCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    role: PersonRole
    employment_type: EmploymentType = EmploymentType.employee
    home_base_location_id: str | None = None
    current_location_id: str | None = None
    availability_status: ResourceStatus = ResourceStatus.available
    max_daily_hours: Decimal = Field(default=Decimal("8.0"), gt=0)
    max_weekly_hours: Decimal = Field(default=Decimal("40.0"), gt=0)
    cost_per_hour: Decimal | None = Field(default=None, ge=0)
    reliability_notes: str | None = None
    active: bool = True


class PersonUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: PersonRole | None = None
    employment_type: EmploymentType | None = None
    home_base_location_id: str | None = None
    current_location_id: str | None = None
    availability_status: ResourceStatus | None = None
    max_daily_hours: Decimal | None = Field(default=None, gt=0)
    max_weekly_hours: Decimal | None = Field(default=None, gt=0)
    cost_per_hour: Decimal | None = Field(default=None, ge=0)
    reliability_notes: str | None = None
    active: bool | None = None


class PersonSkillAssign(BaseModel):
    skill_id: str
    skill_level: int = Field(ge=1, le=5)
    certified: bool = False
    notes: str | None = None


class PersonSkillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    person_id: str
    skill_id: str
    skill_level: int
    certified: bool
    notes: str | None


class PersonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    person_id: str
    full_name: str
    role: PersonRole
    employment_type: EmploymentType
    home_base_location_id: str | None
    current_location_id: str | None
    availability_status: ResourceStatus
    max_daily_hours: Decimal
    max_weekly_hours: Decimal
    cost_per_hour: Decimal | None
    reliability_notes: str | None
    active: bool
    created_at: datetime
    updated_at: datetime


class PersonListResponse(BaseModel):
    items: list[PersonRead]
    total: int
    limit: int
    offset: int


class EquipmentTypeCreate(BaseModel):
    type_name: str = Field(min_length=1, max_length=120)
    category: str | None = None
    description: str | None = None
    default_setup_minutes: int | None = Field(default=None, ge=0)
    default_teardown_minutes: int | None = Field(default=None, ge=0)


class EquipmentTypeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    equipment_type_id: str
    type_name: str
    category: str | None
    description: str | None
    default_setup_minutes: int | None
    default_teardown_minutes: int | None


class EquipmentTypeListResponse(BaseModel):
    items: list[EquipmentTypeRead]
    total: int
    limit: int
    offset: int


class EquipmentCreate(BaseModel):
    equipment_type_id: str
    asset_tag: str | None = None
    serial_number: str | None = None
    status: ResourceStatus = ResourceStatus.available
    warehouse_location_id: str | None = None
    current_location_id: str | None = None
    transport_requirements: str | None = None
    replacement_available: bool = False
    hourly_cost_estimate: Decimal | None = Field(default=None, ge=0)
    purchase_date: date | None = None
    notes: str | None = None
    active: bool = True


class EquipmentUpdate(BaseModel):
    equipment_type_id: str | None = None
    asset_tag: str | None = None
    serial_number: str | None = None
    status: ResourceStatus | None = None
    warehouse_location_id: str | None = None
    current_location_id: str | None = None
    transport_requirements: str | None = None
    replacement_available: bool | None = None
    hourly_cost_estimate: Decimal | None = Field(default=None, ge=0)
    purchase_date: date | None = None
    notes: str | None = None
    active: bool | None = None


class EquipmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    equipment_id: str
    equipment_type_id: str
    asset_tag: str | None
    serial_number: str | None
    status: ResourceStatus
    warehouse_location_id: str | None
    current_location_id: str | None
    transport_requirements: str | None
    replacement_available: bool
    hourly_cost_estimate: Decimal | None
    purchase_date: date | None
    notes: str | None
    active: bool
    created_at: datetime
    updated_at: datetime


class EquipmentListResponse(BaseModel):
    items: list[EquipmentRead]
    total: int
    limit: int
    offset: int


class VehicleCreate(BaseModel):
    vehicle_name: str = Field(min_length=1, max_length=120)
    vehicle_type: VehicleType
    registration_number: str | None = None
    capacity_notes: str | None = None
    status: ResourceStatus = ResourceStatus.available
    home_location_id: str | None = None
    current_location_id: str | None = None
    cost_per_km: Decimal | None = Field(default=None, ge=0)
    cost_per_hour: Decimal | None = Field(default=None, ge=0)
    active: bool = True


class VehicleUpdate(BaseModel):
    vehicle_name: str | None = Field(default=None, min_length=1, max_length=120)
    vehicle_type: VehicleType | None = None
    registration_number: str | None = None
    capacity_notes: str | None = None
    status: ResourceStatus | None = None
    home_location_id: str | None = None
    current_location_id: str | None = None
    cost_per_km: Decimal | None = Field(default=None, ge=0)
    cost_per_hour: Decimal | None = Field(default=None, ge=0)
    active: bool | None = None


class VehicleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    vehicle_id: str
    vehicle_name: str
    vehicle_type: VehicleType
    registration_number: str | None
    capacity_notes: str | None
    status: ResourceStatus
    home_location_id: str | None
    current_location_id: str | None
    cost_per_km: Decimal | None
    cost_per_hour: Decimal | None
    active: bool
    created_at: datetime
    updated_at: datetime


class VehicleListResponse(BaseModel):
    items: list[VehicleRead]
    total: int
    limit: int
    offset: int
