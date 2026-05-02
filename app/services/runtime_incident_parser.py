from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.ops import OpsIncidentSeverity, OpsIncidentType
from app.schemas.runtime_ops import (
    RuntimeIncidentParseRequest,
    RuntimeIncidentParseResponse,
    RuntimeIncidentRequest,
)
from app.services.ai_prompt_templates import build_incident_parsing_prompt
from app.services.azure_openai_service import AzureOpenAIClient
from app.services.runtime_ops_service import report_incident


class RuntimeIncidentParsingError(ValueError):
    pass


class AICompletionProtocol(Protocol):
    content: str


class AIClientProtocol(Protocol):
    def chat_completion(self, template: Any, **kwargs: Any) -> AICompletionProtocol:
        ...


class ParsedIncidentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_type: OpsIncidentType
    severity: OpsIncidentSeverity
    description: str
    root_cause: str | None = None
    sla_impact: bool = False
    cost_impact: Decimal | None = None
    reported_by: str | None = None


@dataclass
class IncidentParseResult:
    incident_type: OpsIncidentType
    severity: OpsIncidentSeverity
    description: str
    root_cause: str | None
    sla_impact: bool
    cost_impact: Decimal | None
    reported_by: str | None
    parser_mode: str
    parse_confidence: float


def parse_and_report_incident(
    db: Session,
    *,
    event_id: str,
    payload: RuntimeIncidentParseRequest,
    actor_user_id: str | None = None,
    actor_username: str | None = None,
    llm_client: AIClientProtocol | None = None,
) -> RuntimeIncidentParseResponse:
    parse_result = _parse_operator_log(payload, llm_client=llm_client)
    incident_payload = RuntimeIncidentRequest(
        assignment_id=payload.assignment_id,
        incident_type=parse_result.incident_type,
        severity=parse_result.severity,
        reported_at=payload.reported_at,
        reported_by=payload.reported_by or parse_result.reported_by,
        root_cause=parse_result.root_cause,
        description=parse_result.description,
        cost_impact=parse_result.cost_impact,
        sla_impact=parse_result.sla_impact,
        author_type=payload.author_type,
        author_reference=payload.author_reference,
    )
    incident_response = report_incident(
        db,
        event_id=event_id,
        payload=incident_payload,
        actor_user_id=actor_user_id,
        actor_username=actor_username,
    )
    return RuntimeIncidentParseResponse(
        event_id=incident_response.event_id,
        incident_id=incident_response.incident_id,
        log_id=incident_response.log_id,
        incident_type=parse_result.incident_type.value,
        severity=parse_result.severity.value,
        description=parse_result.description,
        root_cause=parse_result.root_cause,
        sla_impact=parse_result.sla_impact,
        cost_impact=parse_result.cost_impact,
        reported_by=payload.reported_by or parse_result.reported_by,
        parser_mode=parse_result.parser_mode,
        parse_confidence=parse_result.parse_confidence,
    )


def _parse_operator_log(
    payload: RuntimeIncidentParseRequest, llm_client: AIClientProtocol | None = None
) -> IncidentParseResult:
    if payload.prefer_llm:
        llm_parsed = _parse_with_llm(payload.raw_log, llm_client=llm_client)
        if llm_parsed is not None:
            return llm_parsed
    return _parse_with_heuristics(payload.raw_log)


def _parse_with_llm(
    raw_log: str, llm_client: AIClientProtocol | None = None
) -> IncidentParseResult | None:
    own_client: AzureOpenAIClient | None = None
    try:
        client = llm_client
        if client is None:
            settings = get_settings()
            own_client = AzureOpenAIClient(settings=settings)
            client = own_client

        completion = client.chat_completion(
            build_incident_parsing_prompt(raw_log),
            temperature=0.0,
            max_output_tokens=220,
        )
        parsed = _extract_payload_from_content(completion.content)
        return IncidentParseResult(
            incident_type=parsed.incident_type,
            severity=parsed.severity,
            description=parsed.description.strip(),
            root_cause=_normalize_optional_text(parsed.root_cause),
            sla_impact=bool(parsed.sla_impact),
            cost_impact=parsed.cost_impact,
            reported_by=_normalize_optional_text(parsed.reported_by),
            parser_mode="llm",
            parse_confidence=0.9,
        )
    except Exception:
        return None
    finally:
        if own_client is not None:
            own_client.close()


def _extract_payload_from_content(content: str) -> ParsedIncidentPayload:
    normalized = content.strip()
    if normalized.startswith("```"):
        normalized = normalized.removeprefix("```json").removeprefix("```").strip()
        if normalized.endswith("```"):
            normalized = normalized[:-3].strip()
    try:
        data = json.loads(normalized)
    except Exception as exc:
        raise RuntimeIncidentParsingError("Incident parser returned invalid JSON.") from exc
    try:
        return ParsedIncidentPayload.model_validate(data)
    except ValidationError as exc:
        raise RuntimeIncidentParsingError("Incident parser schema validation failed.") from exc


def _parse_with_heuristics(raw_log: str) -> IncidentParseResult:
    text = raw_log.strip()
    lower = text.lower()

    incident_type = OpsIncidentType.other
    if any(token in lower for token in ["delay", "opozn", "late"]):
        incident_type = OpsIncidentType.delay
    if any(token in lower for token in ["traffic", "korek", "road"]):
        incident_type = OpsIncidentType.traffic_issue
    if any(token in lower for token in ["weather", "storm", "rain", "snieg"]):
        incident_type = OpsIncidentType.weather_issue
    if any(token in lower for token in ["broken", "failure", "awaria", "zepsu", "console"]):
        incident_type = OpsIncidentType.equipment_failure
    if any(token in lower for token in ["absence", "absent", "nieobecn", "sick"]):
        incident_type = OpsIncidentType.staff_absence
    if any(token in lower for token in ["client change", "change request", "zmiana klient"]):
        incident_type = OpsIncidentType.client_change_request
    if any(token in lower for token in ["venue access", "gate blocked", "brak wjazdu"]):
        incident_type = OpsIncidentType.venue_access_issue
    if any(token in lower for token in ["safety", "wypadek", "hazard"]):
        incident_type = OpsIncidentType.safety_issue
    if any(token in lower for token in ["sla", "deadline breach", "krytyczne opoznienie"]):
        incident_type = OpsIncidentType.sla_risk

    severity = OpsIncidentSeverity.medium
    if any(token in lower for token in ["critical", "kryty", "blokada", "major outage"]):
        severity = OpsIncidentSeverity.critical
    elif any(token in lower for token in ["high", "powaz", "duzy impact"]):
        severity = OpsIncidentSeverity.high
    elif any(token in lower for token in ["low", "minor", "niewielk"]):
        severity = OpsIncidentSeverity.low

    sla_impact = any(token in lower for token in ["sla", "deadline", "spozni", "late"])
    cost_impact = _extract_cost_impact(raw_log)
    root_cause = _extract_root_cause(raw_log)
    reported_by = _extract_reported_by(raw_log)

    description = text if text else "Operator incident note."
    return IncidentParseResult(
        incident_type=incident_type,
        severity=severity,
        description=description,
        root_cause=root_cause,
        sla_impact=sla_impact,
        cost_impact=cost_impact,
        reported_by=reported_by,
        parser_mode="heuristic",
        parse_confidence=0.65,
    )


def _extract_cost_impact(raw_log: str) -> Decimal | None:
    matches = re.findall(r"(\d+[.,]?\d{0,2})\s*(?:pln|zl|zł|usd|eur)?", raw_log.lower())
    if not matches:
        return None
    value = matches[0].replace(",", ".")
    try:
        return Decimal(value).quantize(Decimal("0.01"))
    except Exception:
        return None


def _extract_root_cause(raw_log: str) -> str | None:
    patterns = [
        r"(?:because|powod|przyczyna)\s*[:\-]\s*([^\n\.]+)",
        r"(?:due to)\s*([^\n\.]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw_log, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if value:
                return value
    return None


def _extract_reported_by(raw_log: str) -> str | None:
    match = re.search(r"(?:reported by|zglosil|zgłosił)\s*[:\-]?\s*([^\n,]+)", raw_log, flags=re.IGNORECASE)
    if match:
        value = match.group(1).strip()
        if value:
            return value
    return None


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
