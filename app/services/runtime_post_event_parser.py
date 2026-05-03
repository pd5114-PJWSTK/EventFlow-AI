from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, ValidationError

from app.config import get_settings
from app.schemas.runtime_ops import RuntimeCompleteRequest
from app.services.ai_prompt_templates import build_post_event_summary_prompt
from app.services.azure_openai_service import AzureOpenAIClient


class RuntimePostEventParsingError(ValueError):
    pass


class AICompletionProtocol(Protocol):
    content: str


class AIClientProtocol(Protocol):
    def chat_completion(self, template: Any, **kwargs: Any) -> AICompletionProtocol:
        ...


class ParsedPostEventPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finished_on_time: bool | None = None
    total_delay_minutes: int | None = None
    actual_cost: Decimal | None = None
    overtime_cost: Decimal | None = None
    transport_cost: Decimal | None = None
    sla_breached: bool = False
    client_satisfaction_score: Decimal | None = None
    internal_quality_score: Decimal | None = None
    margin_estimate: Decimal | None = None
    summary_notes: str


@dataclass
class PostEventParseResult:
    completion: RuntimeCompleteRequest
    parser_mode: str
    parse_confidence: float
    gaps: list[str]


def parse_post_event_summary(
    *,
    raw_summary: str,
    prefer_llm: bool,
    llm_client: AIClientProtocol | None = None,
) -> PostEventParseResult:
    if prefer_llm:
        llm = _parse_with_llm(raw_summary, llm_client=llm_client)
        if llm is not None:
            return llm
    return _parse_with_heuristics(raw_summary)


def _parse_with_llm(raw_summary: str, llm_client: AIClientProtocol | None = None) -> PostEventParseResult | None:
    own_client: AzureOpenAIClient | None = None
    try:
        client = llm_client
        if client is None:
            settings = get_settings()
            own_client = AzureOpenAIClient(settings=settings)
            client = own_client

        completion = client.chat_completion(
            build_post_event_summary_prompt(raw_summary),
            temperature=0.0,
            max_output_tokens=260,
        )
        parsed = _extract_payload_from_content(completion.content)
        completion_payload = RuntimeCompleteRequest(
            completed_at=datetime.now(UTC),
            finished_on_time=parsed.finished_on_time,
            total_delay_minutes=parsed.total_delay_minutes,
            actual_cost=parsed.actual_cost,
            overtime_cost=parsed.overtime_cost,
            transport_cost=parsed.transport_cost,
            sla_breached=bool(parsed.sla_breached),
            client_satisfaction_score=parsed.client_satisfaction_score,
            internal_quality_score=parsed.internal_quality_score,
            margin_estimate=parsed.margin_estimate,
            summary_notes=parsed.summary_notes,
            message="Event completion imported from post-event summary.",
        )
        return PostEventParseResult(
            completion=completion_payload,
            parser_mode="llm",
            parse_confidence=0.9,
            gaps=_detect_gaps(completion_payload),
        )
    except Exception:
        return None
    finally:
        if own_client is not None:
            own_client.close()


def _parse_with_heuristics(raw_summary: str) -> PostEventParseResult:
    lower = raw_summary.lower()

    finished_on_time: bool | None = None
    if "na czas" in lower or "on time" in lower:
        finished_on_time = True
    if any(token in lower for token in ["opozn", "spozn", "delay", "late"]):
        finished_on_time = False

    delay = _extract_int(raw_summary, pattern=r"(\d+)\s*(?:min|minut|minutes)")
    if finished_on_time is True:
        delay = delay or 0

    actual_cost = _extract_money(raw_summary, ["koszt", "cost"]) 
    overtime_cost = _extract_money(raw_summary, ["nadgodzin", "overtime"]) 
    transport_cost = _extract_money(raw_summary, ["transport"]) 

    sla_breached = any(token in lower for token in ["sla breach", "naruszenie sla", "breach sla"])

    completion_payload = RuntimeCompleteRequest(
        completed_at=datetime.now(UTC),
        finished_on_time=finished_on_time,
        total_delay_minutes=delay,
        actual_cost=actual_cost,
        overtime_cost=overtime_cost,
        transport_cost=transport_cost,
        sla_breached=sla_breached,
        summary_notes=raw_summary.strip(),
        message="Event completion imported from post-event summary.",
    )
    return PostEventParseResult(
        completion=completion_payload,
        parser_mode="heuristic",
        parse_confidence=0.65,
        gaps=_detect_gaps(completion_payload),
    )


def _extract_payload_from_content(content: str) -> ParsedPostEventPayload:
    normalized = content.strip()
    if normalized.startswith("```"):
        normalized = normalized.removeprefix("```json").removeprefix("```").strip()
        if normalized.endswith("```"):
            normalized = normalized[:-3].strip()
    try:
        data = json.loads(normalized)
    except Exception as exc:
        raise RuntimePostEventParsingError("Post-event parser returned invalid JSON.") from exc
    try:
        return ParsedPostEventPayload.model_validate(data)
    except ValidationError as exc:
        raise RuntimePostEventParsingError("Post-event parser schema validation failed.") from exc


def _extract_int(text: str, *, pattern: str) -> int | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    try:
        return int(match.group(1))
    except Exception:
        return None


def _extract_money(text: str, keywords: list[str]) -> Decimal | None:
    lowered = text.lower()
    for keyword in keywords:
        idx = lowered.find(keyword)
        if idx < 0:
            continue
        window = text[idx: idx + 120]
        match = re.search(r"(\d+[\.,]?\d{0,2})", window)
        if not match:
            continue
        value = match.group(1).replace(",", ".")
        try:
            return Decimal(value).quantize(Decimal("0.01"))
        except Exception:
            continue
    return None


def _detect_gaps(completion: RuntimeCompleteRequest) -> list[str]:
    gaps: list[str] = []
    if completion.finished_on_time is None:
        gaps.append("Brak informacji czy event zakonczyl sie na czas.")
    if completion.total_delay_minutes is None:
        gaps.append("Brak informacji o opoznieniu (minuty).")
    if completion.actual_cost is None:
        gaps.append("Brak rzeczywistego kosztu eventu.")
    if completion.client_satisfaction_score is None:
        gaps.append("Brak oceny satysfakcji klienta.")
    if completion.internal_quality_score is None:
        gaps.append("Brak wewnetrznej oceny jakosci.")
    return gaps