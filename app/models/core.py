from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, SmallInteger, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.database import Base


settings = get_settings()
CORE_SCHEMA = None if settings.database_url.startswith("sqlite") else "core"


def _core_table(name: str) -> str:
    if CORE_SCHEMA:
        return f"{CORE_SCHEMA}.{name}"
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

    events: Mapped[list[Event]] = relationship(back_populates="client", cascade="all,delete")


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    client: Mapped[Client] = relationship(back_populates="events")
    location: Mapped[Location] = relationship(back_populates="events")
