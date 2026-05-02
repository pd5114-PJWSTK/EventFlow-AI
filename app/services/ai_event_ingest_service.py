from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.core import (
    Client,
    EquipmentType,
    Location,
    LocationType,
    PersonRole,
    PriorityLevel,
    RequirementType,
    VehicleType,
)
from app.schemas.ai_agents import AIAgentsIngestEventResponse
from app.schemas.events import EventCreate
from app.schemas.requirements import EventRequirementCreate
from app.services.ai_orchestration_service import run_ai_optimization
from app.services.event_service import create_event
from app.services.requirement_service import create_requirement


class AIEventIngestError(ValueError):
    pass


def ingest_event_from_text(
    db: Session,
    *,
    raw_input: str,
    initiated_by: str | None,
    prefer_langgraph: bool,
) -> AIAgentsIngestEventResponse:
    try:
        parsed = _parse_structured_lines(raw_input)
        assumptions = list(parsed["assumptions"])
        parser_mode = "deterministic"
        used_fallback = False

        try:
            llm_result = run_ai_optimization(
                raw_input=raw_input,
                planner_snapshot="",
                prefer_langgraph=prefer_langgraph,
            )
            assumptions.extend(llm_result.parsed_input.assumptions)
            if llm_result.used_fallback:
                used_fallback = True
            requirements = _merge_requirements(
                deterministic_requirements=parsed["requirements"],
                llm_requirements=llm_result.parsed_input.requirements,
            )
        except Exception:
            requirements = parsed["requirements"]
            used_fallback = True
            parser_mode = "deterministic_fallback"
        else:
            parser_mode = "hybrid_llm"

        client = Client(
            name=str(parsed["client_name"]),
            priority=_priority(parsed["client_priority"]),
            notes="Created by AI ingest pipeline.",
        )
        db.add(client)
        db.flush()

        location = Location(
            name=str(parsed["location_name"]),
            city=str(parsed["city"]),
            location_type=_location_type(parsed["location_type"]),
            setup_complexity_score=int(parsed["setup_complexity"]),
            access_difficulty=int(parsed["access_difficulty"]),
            parking_difficulty=int(parsed["parking_difficulty"]),
            notes="Created by AI ingest pipeline.",
        )
        db.add(location)
        db.flush()

        event_payload = EventCreate(
            client_id=client.client_id,
            location_id=location.location_id,
            event_name=str(parsed["event_name"]),
            event_type=str(parsed["event_type"]),
            event_subtype=str(parsed["event_subtype"]) if parsed["event_subtype"] else None,
            attendee_count=int(parsed["attendee_count"]),
            planned_start=parsed["planned_start"],
            planned_end=parsed["planned_end"],
            priority=_priority(parsed["event_priority"]),
            budget_estimate=Decimal(str(parsed["budget_estimate"])),
            requires_transport=bool(parsed["requires_transport"]),
            requires_setup=bool(parsed["requires_setup"]),
            requires_teardown=bool(parsed["requires_teardown"]),
            source_channel="ai_ingest",
            created_by=initiated_by or "ai_ingest",
            notes="Created by AI ingest pipeline.",
        )
        event = create_event(db, event_payload)

        requirement_ids: list[str] = []
        for requirement in requirements:
            payload = dict(requirement)
            if payload.get("requirement_type") == RequirementType.equipment_type:
                payload["equipment_type_id"] = _resolve_equipment_type_id(
                    db, str(payload.get("equipment_type_id"))
                )
            created = create_requirement(
                db,
                event.event_id,
                EventRequirementCreate(**payload),
            )
            requirement_ids.append(created.requirement_id)

        return AIAgentsIngestEventResponse(
            client_id=client.client_id,
            location_id=location.location_id,
            event_id=event.event_id,
            requirement_ids=requirement_ids,
            assumptions=assumptions,
            parser_mode=parser_mode,
            used_fallback=used_fallback,
        )
    except Exception as exc:
        raise AIEventIngestError(str(exc)) from exc


def _parse_structured_lines(raw_input: str) -> dict:
    lines = [line.strip() for line in raw_input.splitlines() if line.strip()]
    kv: dict[str, str] = {}
    for line in lines:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        kv[key.strip().lower()] = value.strip()

    now = datetime.now(UTC).replace(second=0, microsecond=0)
    planned_start = _parse_datetime(kv.get("planned_start")) or (now + timedelta(days=14))
    planned_end = _parse_datetime(kv.get("planned_end")) or (planned_start + timedelta(hours=6))
    if planned_end <= planned_start:
        planned_end = planned_start + timedelta(hours=6)

    assumptions: list[str] = []
    requirements: list[dict] = []
    requirements.extend(_requirements_from_kv(kv))
    if not requirements:
        requirements.append(
            {
                "requirement_type": RequirementType.person_role,
                "role_required": PersonRole.coordinator,
                "quantity": Decimal("1"),
                "mandatory": True,
            }
        )
        assumptions.append("Defaulted missing requirements to one coordinator role.")

    return {
        "client_name": kv.get("client_name", "AI Ingest Client"),
        "client_priority": kv.get("client_priority", "medium"),
        "location_name": kv.get("location_name", "AI Ingest Venue"),
        "city": kv.get("city", "Warsaw"),
        "location_type": kv.get("location_type", "conference_center"),
        "setup_complexity": _int_or_default(kv.get("setup_complexity"), 6, 1, 10),
        "access_difficulty": _int_or_default(kv.get("access_difficulty"), 3, 1, 5),
        "parking_difficulty": _int_or_default(kv.get("parking_difficulty"), 3, 1, 5),
        "event_name": kv.get("event_name", "AI Ingest Event"),
        "event_type": kv.get("event_type", "conference"),
        "event_subtype": kv.get("event_subtype", "touring"),
        "attendee_count": _int_or_default(kv.get("attendee_count"), 200, 0, 50000),
        "planned_start": planned_start,
        "planned_end": planned_end,
        "event_priority": kv.get("event_priority", "medium"),
        "budget_estimate": _decimal_or_default(kv.get("budget_estimate"), Decimal("50000")),
        "requires_transport": _bool_or_default(kv.get("requires_transport"), True),
        "requires_setup": _bool_or_default(kv.get("requires_setup"), True),
        "requires_teardown": _bool_or_default(kv.get("requires_teardown"), True),
        "requirements": requirements,
        "assumptions": assumptions,
    }


def _requirements_from_kv(kv: dict[str, str]) -> list[dict]:
    requirements: list[dict] = []
    for key, value in kv.items():
        if not key.startswith("requirement_"):
            continue
        parts = key.split("_")
        if len(parts) < 3:
            continue
        req_group = parts[1]
        req_name = "_".join(parts[2:])
        quantity = Decimal(str(_int_or_default(value, 0, 0, 1000)))
        if quantity <= 0:
            continue

        if req_group == "person":
            role = _person_role(req_name)
            requirements.append(
                {
                    "requirement_type": RequirementType.person_role,
                    "role_required": role,
                    "quantity": quantity,
                    "mandatory": True,
                }
            )
        elif req_group == "vehicle":
            vehicle = _vehicle_type(req_name)
            requirements.append(
                {
                    "requirement_type": RequirementType.vehicle_type,
                    "vehicle_type_required": vehicle,
                    "quantity": quantity,
                    "mandatory": True,
                }
            )
        elif req_group == "equipment":
            equipment_type_id = _ensure_equipment_type_id(req_name)
            requirements.append(
                {
                    "requirement_type": RequirementType.equipment_type,
                    "equipment_type_id": equipment_type_id,
                    "quantity": quantity,
                    "mandatory": True,
                }
            )
    return requirements


def _merge_requirements(*, deterministic_requirements: list[dict], llm_requirements: list) -> list[dict]:
    merged = list(deterministic_requirements)
    existing_person_roles = {
        str(item.get("role_required")) for item in merged if item.get("requirement_type") == RequirementType.person_role
    }
    existing_vehicle = {
        str(item.get("vehicle_type_required"))
        for item in merged
        if item.get("requirement_type") == RequirementType.vehicle_type
    }

    for req in llm_requirements:
        rtype = (req.requirement_type or "").lower()
        qty = max(int(req.quantity or 1), 1)
        if "driver" in rtype and str(PersonRole.driver) not in existing_person_roles:
            merged.append(
                {
                    "requirement_type": RequirementType.person_role,
                    "role_required": PersonRole.driver,
                    "quantity": Decimal(str(qty)),
                    "mandatory": True,
                }
            )
        elif "coordinator" in rtype and str(PersonRole.coordinator) not in existing_person_roles:
            merged.append(
                {
                    "requirement_type": RequirementType.person_role,
                    "role_required": PersonRole.coordinator,
                    "quantity": Decimal(str(qty)),
                    "mandatory": True,
                }
            )
        elif "vehicle" in rtype or "transport" in rtype:
            if str(VehicleType.van) not in existing_vehicle:
                merged.append(
                    {
                        "requirement_type": RequirementType.vehicle_type,
                        "vehicle_type_required": VehicleType.van,
                        "quantity": Decimal(str(qty)),
                        "mandatory": True,
                    }
                )
        elif "equipment" in rtype:
            merged.append(
                {
                    "requirement_type": RequirementType.equipment_type,
                    "equipment_type_id": _ensure_equipment_type_id("generic"),
                    "quantity": Decimal(str(qty)),
                    "mandatory": True,
                }
            )
    return merged


def _ensure_equipment_type_id(type_name: str) -> str:
    # Sentinel deterministic id handled later by lookup/creation in create flow.
    return f"__AUTO_EQUIPMENT_TYPE__::{type_name.lower().strip()}"


def _resolve_equipment_type_id(db: Session, equipment_type_id: str) -> str:
    if not equipment_type_id.startswith("__AUTO_EQUIPMENT_TYPE__::"):
        return equipment_type_id
    type_name = equipment_type_id.split("::", 1)[1].replace("_", " ").strip() or "generic"
    existing = (
        db.query(EquipmentType)
        .filter(EquipmentType.type_name.ilike(type_name))
        .first()
    )
    if existing is not None:
        return existing.equipment_type_id
    created = EquipmentType(type_name=type_name.title())
    db.add(created)
    db.flush()
    return created.equipment_type_id


def _priority(value: str) -> PriorityLevel:
    normalized = (value or "").strip().lower()
    if normalized in {"low", "medium", "high", "critical"}:
        return PriorityLevel(normalized)
    return PriorityLevel.medium


def _location_type(value: str) -> LocationType:
    normalized = (value or "").strip().lower()
    for item in LocationType:
        if item.value == normalized:
            return item
    return LocationType.conference_center


def _person_role(value: str) -> PersonRole:
    normalized = (value or "").strip().lower()
    mapping = {
        "coordinator": PersonRole.coordinator,
        "driver": PersonRole.driver,
        "stage_manager": PersonRole.stage_manager,
        "technician_audio": PersonRole.technician_audio,
        "technician_light": PersonRole.technician_light,
        "technician_video": PersonRole.technician_video,
    }
    return mapping.get(normalized, PersonRole.coordinator)


def _vehicle_type(value: str) -> VehicleType:
    normalized = (value or "").strip().lower()
    mapping = {
        "van": VehicleType.van,
        "truck": VehicleType.truck,
        "car": VehicleType.car,
        "trailer": VehicleType.trailer,
    }
    return mapping.get(normalized, VehicleType.van)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip().replace("Z", "+00:00")
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(raw, fmt)
            return parsed.replace(tzinfo=UTC)
        except Exception:
            pass
    try:
        parsed = datetime.fromisoformat(raw)
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _int_or_default(value: str | None, default: int, min_value: int, max_value: int) -> int:
    try:
        parsed = int(str(value))
    except Exception:
        parsed = default
    return max(min(parsed, max_value), min_value)


def _decimal_or_default(value: str | None, default: Decimal) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return default


def _bool_or_default(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "tak"}:
        return True
    if normalized in {"0", "false", "no", "n", "nie"}:
        return False
    return default
