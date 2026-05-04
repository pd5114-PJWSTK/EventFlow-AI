from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from app.models.core import Client, EquipmentType, Location, LocationType, PersonRole, PriorityLevel, RequirementType, VehicleType
from app.schemas.ai_agents import (
    AIAgentsIngestEventCommitRequest,
    AIAgentsIngestEventDraftGap,
    AIAgentsIngestEventDraftPayload,
    AIAgentsIngestEventDraftRequirement,
    AIAgentsIngestEventPreviewResponse,
    AIAgentsIngestEventResponse,
)
from app.schemas.events import EventCreate
from app.schemas.requirements import EventRequirementCreate
from app.services.ai_prompt_templates import build_event_intake_prompt
from app.services.ai_orchestration_service import run_ai_optimization
from app.services.azure_openai_service import AzureOpenAIClient
from app.services.event_service import create_event
from app.services.requirement_service import create_requirement


class AIEventIngestError(ValueError):
    pass


class _LLMIntakeRequirement(BaseModel):
    model_config = ConfigDict(extra="ignore")

    requirement_type: str | None = None
    role_required: str | None = None
    equipment_type_name: str | None = None
    vehicle_type_required: str | None = None
    quantity: int | None = Field(default=1, ge=0)
    mandatory: bool = True
    notes: str | None = None


class _LLMIntakePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    client_name: str | None = None
    client_priority: str | None = None
    location_name: str | None = None
    city: str | None = None
    location_type: str | None = None
    setup_complexity_score: int | None = None
    access_difficulty: int | None = None
    parking_difficulty: int | None = None
    event_name: str | None = None
    event_type: str | None = None
    event_subtype: str | None = None
    attendee_count: int | None = None
    planned_start: str | None = None
    planned_end: str | None = None
    event_priority: str | None = None
    budget_estimate: Decimal | None = None
    requires_transport: bool | None = None
    requires_setup: bool | None = None
    requires_teardown: bool | None = None
    assumptions: list[str] = Field(default_factory=list)
    requirements: list[_LLMIntakeRequirement] = Field(default_factory=list)


def preview_ingest_event_from_text(
    *,
    raw_input: str,
    initiated_by: str | None,
    prefer_langgraph: bool,
) -> AIAgentsIngestEventPreviewResponse:
    try:
        deterministic = _parse_structured_lines(raw_input)
        parsed = deterministic
        parser_mode = "deterministic"
        used_fallback = False

        if prefer_langgraph:
            try:
                llm_payload = _parse_event_intake_with_llm(raw_input)
                parsed = _merge_intake_payload(deterministic, llm_payload)
                parser_mode = "llm"
            except Exception:
                parser_mode = "deterministic_fallback"
                used_fallback = True
                try:
                    llm_result = run_ai_optimization(
                        raw_input=raw_input,
                        planner_snapshot="",
                        prefer_langgraph=prefer_langgraph,
                    )
                    parsed["assumptions"].extend(llm_result.parsed_input.assumptions)
                    parsed["requirements"] = _merge_requirements(
                        deterministic_requirements=list(parsed["requirements"]),
                        llm_requirements=llm_result.parsed_input.requirements,
                    )
                except Exception:
                    pass

        assumptions = list(parsed["assumptions"])
        requirements = list(parsed["requirements"])

        draft = AIAgentsIngestEventDraftPayload(
            client_name=str(parsed["client_name"]),
            client_priority=_priority(str(parsed["client_priority"])),
            location_name=str(parsed["location_name"]),
            city=str(parsed["city"]),
            location_type=_location_type(str(parsed["location_type"])),
            setup_complexity_score=int(parsed["setup_complexity"]),
            access_difficulty=int(parsed["access_difficulty"]),
            parking_difficulty=int(parsed["parking_difficulty"]),
            event_name=str(parsed["event_name"]),
            event_type=str(parsed["event_type"]),
            event_subtype=str(parsed["event_subtype"]) if parsed["event_subtype"] else None,
            attendee_count=int(parsed["attendee_count"]),
            planned_start=parsed["planned_start"],
            planned_end=parsed["planned_end"],
            event_priority=_priority(str(parsed["event_priority"])),
            budget_estimate=Decimal(str(parsed["budget_estimate"])),
            requires_transport=bool(parsed["requires_transport"]),
            requires_setup=bool(parsed["requires_setup"]),
            requires_teardown=bool(parsed["requires_teardown"]),
            requirements=[AIAgentsIngestEventDraftRequirement(**requirement) for requirement in requirements],
        )

        gaps = _build_preview_gaps(raw_input=raw_input, draft=draft)
        if not draft.requirements:
            gaps.append(
                AIAgentsIngestEventDraftGap(
                    field="requirements",
                    message="Missing event requirements. Add at least one requirement.",
                    severity="critical",
                )
            )

        return AIAgentsIngestEventPreviewResponse(
            draft=draft,
            assumptions=assumptions,
            gaps=gaps,
            parser_mode=parser_mode,
            used_fallback=used_fallback,
        )
    except Exception as exc:
        raise AIEventIngestError(str(exc)) from exc


def _parse_event_intake_with_llm(raw_input: str) -> _LLMIntakePayload:
    client: AzureOpenAIClient | None = None
    try:
        client = AzureOpenAIClient()
        completion = client.chat_completion(
            build_event_intake_prompt(raw_input),
            temperature=0.0,
            max_output_tokens=500,
        )
        content = completion.content.strip()
        if content.startswith("```"):
            content = content.removeprefix("```json").removeprefix("```").strip()
            if content.endswith("```"):
                content = content[:-3].strip()
        return _LLMIntakePayload.model_validate(json.loads(content))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise AIEventIngestError("LLM intake parser returned invalid event JSON.") from exc
    finally:
        if client is not None:
            client.close()


def _merge_intake_payload(deterministic: dict[str, Any], llm: _LLMIntakePayload) -> dict[str, Any]:
    parsed = dict(deterministic)
    scalar_map = {
        "client_name": llm.client_name,
        "client_priority": llm.client_priority,
        "location_name": llm.location_name,
        "city": llm.city,
        "location_type": llm.location_type,
        "setup_complexity": llm.setup_complexity_score,
        "access_difficulty": llm.access_difficulty,
        "parking_difficulty": llm.parking_difficulty,
        "event_name": llm.event_name,
        "event_type": llm.event_type,
        "event_subtype": llm.event_subtype,
        "attendee_count": llm.attendee_count,
        "event_priority": llm.event_priority,
        "budget_estimate": llm.budget_estimate,
        "requires_transport": llm.requires_transport,
        "requires_setup": llm.requires_setup,
        "requires_teardown": llm.requires_teardown,
    }
    for key, value in scalar_map.items():
        if value is not None and str(value).strip() != "":
            parsed[key] = value

    planned_start = _parse_datetime(llm.planned_start)
    planned_end = _parse_datetime(llm.planned_end)
    if planned_start is not None:
        parsed["planned_start"] = planned_start
    if planned_end is not None:
        parsed["planned_end"] = planned_end
    if parsed["planned_end"] <= parsed["planned_start"]:
        parsed["planned_end"] = parsed["planned_start"] + timedelta(hours=6)

    requirements = _requirements_from_llm(llm.requirements)
    if requirements:
        parsed["requirements"] = requirements
    assumptions = [item.strip() for item in llm.assumptions if item.strip()]
    if assumptions:
        parsed["assumptions"] = assumptions
    return parsed


def _requirements_from_llm(requirements: list[_LLMIntakeRequirement]) -> list[dict]:
    normalized: list[dict] = []
    for requirement in requirements:
        quantity = Decimal(str(max(int(requirement.quantity or 1), 1)))
        rtype = (requirement.requirement_type or "").strip().lower()
        if rtype == "person_role" or requirement.role_required:
            normalized.append(
                {
                    "requirement_type": RequirementType.person_role,
                    "role_required": _person_role(requirement.role_required or "coordinator"),
                    "quantity": quantity,
                    "mandatory": requirement.mandatory,
                    "notes": requirement.notes,
                }
            )
        elif rtype == "vehicle_type" or requirement.vehicle_type_required:
            normalized.append(
                {
                    "requirement_type": RequirementType.vehicle_type,
                    "vehicle_type_required": _vehicle_type(requirement.vehicle_type_required or "van"),
                    "quantity": quantity,
                    "mandatory": requirement.mandatory,
                    "notes": requirement.notes,
                }
            )
        elif rtype == "equipment_type" or requirement.equipment_type_name:
            normalized.append(
                {
                    "requirement_type": RequirementType.equipment_type,
                    "equipment_type_id": _ensure_equipment_type_id(requirement.equipment_type_name or "generic"),
                    "quantity": quantity,
                    "mandatory": requirement.mandatory,
                    "notes": requirement.notes,
                }
            )
    return normalized


def commit_ingest_event_draft(
    db: Session,
    *,
    payload: AIAgentsIngestEventCommitRequest,
    initiated_by_user_id: str | None,
) -> AIAgentsIngestEventResponse:
    try:
        draft = payload.draft
        initiated_by = payload.initiated_by or "ai_ingest"

        client = _resolve_or_create_client(db, draft=draft)
        location = _resolve_or_create_location(db, draft=draft)

        event_payload = EventCreate(
            client_id=client.client_id,
            location_id=location.location_id,
            event_name=draft.event_name,
            event_type=draft.event_type,
            event_subtype=draft.event_subtype,
            attendee_count=draft.attendee_count,
            planned_start=draft.planned_start,
            planned_end=draft.planned_end,
            priority=draft.event_priority,
            budget_estimate=draft.budget_estimate,
            requires_transport=draft.requires_transport,
            requires_setup=draft.requires_setup,
            requires_teardown=draft.requires_teardown,
            source_channel="ai_ingest",
            created_by=initiated_by,
            created_by_user_id=initiated_by_user_id,
            notes="Created by AI ingest pipeline.",
        )
        event = create_event(db, event_payload)

        requirement_ids: list[str] = []
        for requirement in draft.requirements:
            req_payload = requirement.model_dump(mode="json")
            if req_payload.get("requirement_type") == RequirementType.equipment_type:
                req_payload["equipment_type_id"] = _resolve_equipment_type_id(
                    db, str(req_payload.get("equipment_type_id"))
                )
            created = create_requirement(
                db,
                event.event_id,
                EventRequirementCreate(**req_payload),
            )
            requirement_ids.append(created.requirement_id)

        return AIAgentsIngestEventResponse(
            client_id=client.client_id,
            location_id=location.location_id,
            event_id=event.event_id,
            requirement_ids=requirement_ids,
            assumptions=payload.assumptions,
            parser_mode=payload.parser_mode,
            used_fallback=payload.used_fallback,
        )
    except Exception as exc:
        raise AIEventIngestError(str(exc)) from exc


def ingest_event_from_text(
    db: Session,
    *,
    raw_input: str,
    initiated_by: str | None,
    initiated_by_user_id: str | None,
    prefer_langgraph: bool,
) -> AIAgentsIngestEventResponse:
    try:
        preview = preview_ingest_event_from_text(
            raw_input=raw_input,
            initiated_by=initiated_by,
            prefer_langgraph=prefer_langgraph,
        )
        return commit_ingest_event_draft(
            db,
            payload=AIAgentsIngestEventCommitRequest(
                draft=preview.draft,
                assumptions=preview.assumptions,
                parser_mode=preview.parser_mode,
                used_fallback=preview.used_fallback,
                initiated_by=initiated_by,
            ),
            initiated_by_user_id=initiated_by_user_id,
        )
    except Exception as exc:
        raise AIEventIngestError(str(exc)) from exc


def _resolve_or_create_client(db: Session, *, draft: AIAgentsIngestEventDraftPayload) -> Client:
    if draft.client_id:
        client = db.get(Client, draft.client_id)
        if client is None:
            raise AIEventIngestError("client_id z draftu nie istnieje.")
        return client

    client = Client(
        name=draft.client_name,
        priority=draft.client_priority,
        notes="Created by AI ingest pipeline.",
    )
    db.add(client)
    db.flush()
    return client


def _resolve_or_create_location(db: Session, *, draft: AIAgentsIngestEventDraftPayload) -> Location:
    if draft.location_id:
        location = db.get(Location, draft.location_id)
        if location is None:
            raise AIEventIngestError("location_id z draftu nie istnieje.")
        return location

    location = Location(
        name=draft.location_name,
        city=draft.city,
        location_type=draft.location_type,
        setup_complexity_score=draft.setup_complexity_score,
        access_difficulty=draft.access_difficulty,
        parking_difficulty=draft.parking_difficulty,
        notes="Created by AI ingest pipeline.",
    )
    db.add(location)
    db.flush()
    return location


def _build_preview_gaps(*, raw_input: str, draft: AIAgentsIngestEventDraftPayload) -> list[AIAgentsIngestEventDraftGap]:
    gaps: list[AIAgentsIngestEventDraftGap] = []
    kv_keys = {line.split(":", 1)[0].strip().lower() for line in raw_input.splitlines() if ":" in line}

    key_to_field = {
        "client_name": "client_name",
        "location_name": "location_name",
        "city": "city",
        "event_name": "event_name",
        "event_type": "event_type",
        "planned_start": "planned_start",
        "planned_end": "planned_end",
    }
    for key, field_name in key_to_field.items():
        if key not in kv_keys:
            gaps.append(
                AIAgentsIngestEventDraftGap(
                    field=field_name,
                    message=f"Pole {field_name} zostalo uzupelnione domyslnie i wymaga weryfikacji.",
                    severity="warning",
                )
            )

    if draft.planned_end <= draft.planned_start:
        gaps.append(
            AIAgentsIngestEventDraftGap(
                field="planned_end",
                message="planned_end musi byc pozniejszy niz planned_start.",
                severity="critical",
            )
        )
    return gaps


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
