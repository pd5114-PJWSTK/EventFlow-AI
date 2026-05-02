from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.database import Base


settings = get_settings()
CORE_SCHEMA = None if settings.database_url.startswith("sqlite") else "core"
AI_SCHEMA = None if settings.database_url.startswith("sqlite") else "ai"
AUTH_SCHEMA = None if settings.database_url.startswith("sqlite") else "auth"


def _core_table(name: str) -> str:
    if CORE_SCHEMA:
        return f"{CORE_SCHEMA}.{name}"
    return name


def _ai_table(name: str) -> str:
    if AI_SCHEMA:
        return f"{AI_SCHEMA}.{name}"
    return name


def _auth_table(name: str) -> str:
    if AUTH_SCHEMA:
        return f"{AUTH_SCHEMA}.{name}"
    return name


class PriorityLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class LocationType(str, Enum):
    indoor = "indoor"
    outdoor = "outdoor"
    hybrid = "hybrid"
    warehouse = "warehouse"
    conference_center = "conference_center"
    stadium = "stadium"
    office = "office"
    other = "other"


class EventStatus(str, Enum):
    draft = "draft"
    submitted = "submitted"
    validated = "validated"
    planned = "planned"
    confirmed = "confirmed"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class ResourceStatus(str, Enum):
    available = "available"
    reserved = "reserved"
    in_use = "in_use"
    maintenance = "maintenance"
    unavailable = "unavailable"
    retired = "retired"


class PersonRole(str, Enum):
    technician_audio = "technician_audio"
    technician_light = "technician_light"
    technician_video = "technician_video"
    stage_manager = "stage_manager"
    coordinator = "coordinator"
    driver = "driver"
    warehouse_operator = "warehouse_operator"
    project_manager = "project_manager"
    freelancer = "freelancer"
    other = "other"


class EmploymentType(str, Enum):
    employee = "employee"
    contractor = "contractor"
    freelancer = "freelancer"
    agency_staff = "agency_staff"
    other = "other"


class VehicleType(str, Enum):
    van = "van"
    truck = "truck"
    car = "car"
    trailer = "trailer"
    other = "other"


class RequirementType(str, Enum):
    person_skill = "person_skill"
    person_role = "person_role"
    equipment_type = "equipment_type"
    vehicle_type = "vehicle_type"
    time_buffer = "time_buffer"
    other = "other"


class AssignmentResourceType(str, Enum):
    person = "person"
    equipment = "equipment"
    vehicle = "vehicle"


class AssignmentStatus(str, Enum):
    proposed = "proposed"
    planned = "planned"
    confirmed = "confirmed"
    active = "active"
    completed = "completed"
    cancelled = "cancelled"
    failed = "failed"


class Client(Base):
    __tablename__ = "clients"
    __table_args__ = {"schema": CORE_SCHEMA}

    client_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    industry: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[PriorityLevel] = mapped_column(
        SAEnum(PriorityLevel, native_enum=False), default=PriorityLevel.medium, nullable=False
    )
    sla_type: Mapped[str | None] = mapped_column(Text)
    contact_person_name: Mapped[str | None] = mapped_column(Text)
    contact_email: Mapped[str | None] = mapped_column(Text)
    contact_phone: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    events: Mapped[list[Event]] = relationship(back_populates="client")


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = {"schema": CORE_SCHEMA}

    location_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str] = mapped_column(Text, nullable=False)
    address_line: Mapped[str | None] = mapped_column(Text)
    postal_code: Mapped[str | None] = mapped_column(Text)
    country_code: Mapped[str] = mapped_column(String(2), default="PL", nullable=False)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    location_type: Mapped[LocationType] = mapped_column(
        SAEnum(LocationType, native_enum=False), default=LocationType.other, nullable=False
    )
    parking_difficulty: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)
    access_difficulty: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)
    setup_complexity_score: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    events: Mapped[list[Event]] = relationship(back_populates="location")
    people_home_base: Mapped[list[ResourcePerson]] = relationship(back_populates="home_base_location")
    equipment_warehoused: Mapped[list[Equipment]] = relationship(back_populates="warehouse_location")
    vehicles_home_base: Mapped[list[Vehicle]] = relationship(back_populates="home_location")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = {"schema": CORE_SCHEMA}

    event_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    client_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey(_core_table("clients.client_id"), ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey(_core_table("locations.location_id"), ondelete="RESTRICT"), nullable=False
    )
    event_name: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    event_subtype: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    attendee_count: Mapped[int | None] = mapped_column(Integer)
    planned_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planned_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    priority: Mapped[PriorityLevel] = mapped_column(
        SAEnum(PriorityLevel, native_enum=False), default=PriorityLevel.medium, nullable=False
    )
    status: Mapped[EventStatus] = mapped_column(
        SAEnum(EventStatus, native_enum=False), default=EventStatus.draft, nullable=False
    )
    budget_estimate: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency_code: Mapped[str] = mapped_column(String(3), default="PLN", nullable=False)
    source_channel: Mapped[str | None] = mapped_column(Text)
    requires_transport: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    requires_setup: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    requires_teardown: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_auth_table("users.user_id"), ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    client: Mapped[Client] = relationship(back_populates="events")
    location: Mapped[Location] = relationship(back_populates="events")
    requirements: Mapped[list[EventRequirement]] = relationship(back_populates="event", cascade="all,delete-orphan")
    assignments: Mapped[list[Assignment]] = relationship(
        back_populates="event", cascade="all,delete-orphan"
    )
    transport_legs: Mapped[list[TransportLeg]] = relationship(
        back_populates="event", cascade="all,delete-orphan"
    )


class Skill(Base):
    __tablename__ = "skills"
    __table_args__ = {"schema": CORE_SCHEMA}

    skill_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    skill_name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    skill_category: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)

    people_links: Mapped[list[PersonSkill]] = relationship(back_populates="skill", cascade="all,delete-orphan")


class ResourcePerson(Base):
    __tablename__ = "resources_people"
    __table_args__ = {"schema": CORE_SCHEMA}

    person_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[PersonRole] = mapped_column(SAEnum(PersonRole, native_enum=False), nullable=False)
    employment_type: Mapped[EmploymentType] = mapped_column(
        SAEnum(EmploymentType, native_enum=False), default=EmploymentType.employee, nullable=False
    )
    home_base_location_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey(_core_table("locations.location_id"), ondelete="SET NULL")
    )
    availability_status: Mapped[ResourceStatus] = mapped_column(
        SAEnum(ResourceStatus, native_enum=False), default=ResourceStatus.available, nullable=False
    )
    max_daily_hours: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("8.0"), nullable=False)
    max_weekly_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("40.0"), nullable=False)
    cost_per_hour: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    reliability_notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    home_base_location: Mapped[Location | None] = relationship(back_populates="people_home_base")
    skills: Mapped[list[PersonSkill]] = relationship(back_populates="person", cascade="all,delete-orphan")
    availability_windows: Mapped[list[PeopleAvailability]] = relationship(
        back_populates="person",
        cascade="all,delete-orphan",
    )


class PersonSkill(Base):
    __tablename__ = "people_skills"
    __table_args__ = {"schema": CORE_SCHEMA}

    person_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey(_core_table("resources_people.person_id"), ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey(_core_table("skills.skill_id"), ondelete="CASCADE"), primary_key=True
    )
    skill_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    certified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    person: Mapped[ResourcePerson] = relationship(back_populates="skills")
    skill: Mapped[Skill] = relationship(back_populates="people_links")


class EquipmentType(Base):
    __tablename__ = "equipment_types"
    __table_args__ = {"schema": CORE_SCHEMA}

    equipment_type_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    type_name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    category: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    default_setup_minutes: Mapped[int | None] = mapped_column(Integer)
    default_teardown_minutes: Mapped[int | None] = mapped_column(Integer)

    equipment_items: Mapped[list[Equipment]] = relationship(back_populates="equipment_type")


class Equipment(Base):
    __tablename__ = "equipment"
    __table_args__ = {"schema": CORE_SCHEMA}

    equipment_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    equipment_type_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey(_core_table("equipment_types.equipment_type_id"), ondelete="RESTRICT"), nullable=False
    )
    asset_tag: Mapped[str | None] = mapped_column(Text, unique=True)
    serial_number: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ResourceStatus] = mapped_column(
        SAEnum(ResourceStatus, native_enum=False), default=ResourceStatus.available, nullable=False
    )
    warehouse_location_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey(_core_table("locations.location_id"), ondelete="SET NULL")
    )
    transport_requirements: Mapped[str | None] = mapped_column(Text)
    replacement_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hourly_cost_estimate: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    purchase_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    equipment_type: Mapped[EquipmentType] = relationship(back_populates="equipment_items")
    warehouse_location: Mapped[Location | None] = relationship(back_populates="equipment_warehoused")
    availability_windows: Mapped[list[EquipmentAvailability]] = relationship(
        back_populates="equipment",
        cascade="all,delete-orphan",
    )


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = {"schema": CORE_SCHEMA}

    vehicle_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    vehicle_name: Mapped[str] = mapped_column(Text, nullable=False)
    vehicle_type: Mapped[VehicleType] = mapped_column(SAEnum(VehicleType, native_enum=False), nullable=False)
    registration_number: Mapped[str | None] = mapped_column(Text, unique=True)
    capacity_notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ResourceStatus] = mapped_column(
        SAEnum(ResourceStatus, native_enum=False), default=ResourceStatus.available, nullable=False
    )
    home_location_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey(_core_table("locations.location_id"), ondelete="SET NULL")
    )
    cost_per_km: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    cost_per_hour: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    home_location: Mapped[Location | None] = relationship(back_populates="vehicles_home_base")
    availability_windows: Mapped[list[VehicleAvailability]] = relationship(
        back_populates="vehicle",
        cascade="all,delete-orphan",
    )


class EventRequirement(Base):
    __tablename__ = "event_requirements"
    __table_args__ = {"schema": CORE_SCHEMA}

    requirement_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    event_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("events.event_id"), ondelete="CASCADE"),
        nullable=False,
    )
    requirement_type: Mapped[RequirementType] = mapped_column(
        SAEnum(RequirementType, native_enum=False),
        nullable=False,
    )
    role_required: Mapped[PersonRole | None] = mapped_column(SAEnum(PersonRole, native_enum=False))
    skill_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("skills.skill_id"), ondelete="SET NULL"),
    )
    equipment_type_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("equipment_types.equipment_type_id"), ondelete="SET NULL"),
    )
    vehicle_type_required: Mapped[VehicleType | None] = mapped_column(SAEnum(VehicleType, native_enum=False))
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("1"), nullable=False)
    mandatory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    required_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    required_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    event: Mapped[Event] = relationship(back_populates="requirements")
    skill: Mapped[Skill | None] = relationship()
    equipment_type: Mapped[EquipmentType | None] = relationship()


class PeopleAvailability(Base):
    __tablename__ = "people_availability"
    __table_args__ = {"schema": CORE_SCHEMA}

    availability_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    person_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("resources_people.person_id"), ondelete="CASCADE"),
        nullable=False,
    )
    available_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    available_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source: Mapped[str | None] = mapped_column(Text, default="manual")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    person: Mapped[ResourcePerson] = relationship(back_populates="availability_windows")


class EquipmentAvailability(Base):
    __tablename__ = "equipment_availability"
    __table_args__ = {"schema": CORE_SCHEMA}

    availability_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    equipment_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("equipment.equipment_id"), ondelete="CASCADE"),
        nullable=False,
    )
    available_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    available_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source: Mapped[str | None] = mapped_column(Text, default="system")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    equipment: Mapped[Equipment] = relationship(back_populates="availability_windows")


class VehicleAvailability(Base):
    __tablename__ = "vehicle_availability"
    __table_args__ = {"schema": CORE_SCHEMA}

    availability_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    vehicle_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("vehicles.vehicle_id"), ondelete="CASCADE"),
        nullable=False,
    )
    available_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    available_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source: Mapped[str | None] = mapped_column(Text, default="system")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    vehicle: Mapped[Vehicle] = relationship(back_populates="availability_windows")


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (
        CheckConstraint(
            "planned_end > planned_start",
            name="ck_assignments_time_window",
        ),
        CheckConstraint(
            "(consumed_at IS NULL) OR (consumed_at >= created_at)",
            name="ck_assignments_consumed_after_create",
        ),
        CheckConstraint(
            "("
            "(resource_type = 'person' AND person_id IS NOT NULL AND equipment_id IS NULL AND vehicle_id IS NULL) OR "
            "(resource_type = 'equipment' AND equipment_id IS NOT NULL AND person_id IS NULL AND vehicle_id IS NULL) OR "
            "(resource_type = 'vehicle' AND vehicle_id IS NOT NULL AND person_id IS NULL AND equipment_id IS NULL)"
            ")",
            name="ck_assignments_resource_identity",
        ),
        Index(
            "uq_assignments_person_active_slot",
            "event_id",
            "person_id",
            "planned_start",
            "planned_end",
            "status",
            unique=True,
            postgresql_where=text("resource_type = 'person'"),
            sqlite_where=text("resource_type = 'person'"),
        ),
        Index(
            "uq_assignments_equipment_active_slot",
            "event_id",
            "equipment_id",
            "planned_start",
            "planned_end",
            "status",
            unique=True,
            postgresql_where=text("resource_type = 'equipment'"),
            sqlite_where=text("resource_type = 'equipment'"),
        ),
        Index(
            "uq_assignments_vehicle_active_slot",
            "event_id",
            "vehicle_id",
            "planned_start",
            "planned_end",
            "status",
            unique=True,
            postgresql_where=text("resource_type = 'vehicle'"),
            sqlite_where=text("resource_type = 'vehicle'"),
        ),
        Index(
            "ix_assignments_event_window_status",
            "event_id",
            "planned_start",
            "planned_end",
            "status",
        ),
        Index(
            "ix_assignments_person_window_status",
            "person_id",
            "planned_start",
            "planned_end",
            "status",
        ),
        Index(
            "ix_assignments_equipment_window_status",
            "equipment_id",
            "planned_start",
            "planned_end",
            "status",
        ),
        Index(
            "ix_assignments_vehicle_window_status",
            "vehicle_id",
            "planned_start",
            "planned_end",
            "status",
        ),
        {"schema": CORE_SCHEMA},
    )

    assignment_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    event_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("events.event_id"), ondelete="CASCADE"),
        nullable=False,
    )
    resource_type: Mapped[AssignmentResourceType] = mapped_column(
        SAEnum(AssignmentResourceType, native_enum=False), nullable=False
    )
    person_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("resources_people.person_id"), ondelete="CASCADE"),
    )
    equipment_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("equipment.equipment_id"), ondelete="CASCADE"),
    )
    vehicle_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("vehicles.vehicle_id"), ondelete="CASCADE"),
    )
    assignment_role: Mapped[str | None] = mapped_column(Text)
    planned_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    planned_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[AssignmentStatus] = mapped_column(
        SAEnum(AssignmentStatus, native_enum=False),
        default=AssignmentStatus.planned,
        nullable=False,
    )
    planner_run_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_ai_table("planner_runs.planner_run_id"), ondelete="SET NULL"),
    )
    is_manual_override: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    is_consumed_in_execution: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    event: Mapped[Event] = relationship(back_populates="assignments")
    person: Mapped[ResourcePerson | None] = relationship()
    equipment: Mapped[Equipment | None] = relationship()
    vehicle: Mapped[Vehicle | None] = relationship()


class TransportLeg(Base):
    __tablename__ = "transport_legs"
    __table_args__ = {"schema": CORE_SCHEMA}

    transport_leg_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    event_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("events.event_id"), ondelete="CASCADE"),
        nullable=False,
    )
    vehicle_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("vehicles.vehicle_id"), ondelete="SET NULL"),
    )
    driver_person_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("resources_people.person_id"), ondelete="SET NULL"),
    )
    origin_location_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("locations.location_id"), ondelete="RESTRICT"),
        nullable=False,
    )
    destination_location_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey(_core_table("locations.location_id"), ondelete="RESTRICT"),
        nullable=False,
    )
    planned_departure: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    planned_arrival: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    estimated_distance_km: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    estimated_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    event: Mapped[Event] = relationship(back_populates="transport_legs")
    vehicle: Mapped[Vehicle | None] = relationship()
    driver: Mapped[ResourcePerson | None] = relationship()
    origin_location: Mapped[Location] = relationship(
        foreign_keys=[origin_location_id]
    )
    destination_location: Mapped[Location] = relationship(
        foreign_keys=[destination_location_id]
    )
