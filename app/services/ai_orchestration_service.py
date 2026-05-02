from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import Settings, get_settings
from app.services.ai_prompt_templates import (
    build_optimization_prompt,
    build_parsing_prompt,
    build_risk_explanation_prompt,
)
from app.services.azure_openai_service import AzureOpenAIClient


try:
    from langgraph.graph import END, StateGraph

    _LANGGRAPH_AVAILABLE = False
except Exception:
    END = "__end__"
    StateGraph = None
    _LANGGRAPH_AVAILABLE = False


class AIOrchestrationError(RuntimeError):
    pass


class AICompletionProtocol(Protocol):
    content: str


class AIClientProtocol(Protocol):
    def chat_completion(self, template: Any, **kwargs: Any) -> AICompletionProtocol:
        ...


class ParsedRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement_type: str = Field(min_length=1)
    quantity: int = Field(default=1, ge=1)
    notes: str | None = None


class ParsedPlanningInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_name: str | None = None
    requirements: list[ParsedRequirement] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class OptimizationProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    changes: list[str]
    tradeoffs: list[str]


class RiskEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_risk: Literal["low", "medium", "high"]
    top_risks: list[str]
    mitigations: list[str]


@dataclass
class AIOrchestrationResult:
    parsed_input: ParsedPlanningInput
    optimization: OptimizationProposal
    evaluation: RiskEvaluation
    used_fallback: bool
    fallback_steps: list[str] = field(default_factory=list)
    execution_mode: Literal["langgraph", "sequential"] = "sequential"


@dataclass
class AIOptimizationResult:
    parsed_input: ParsedPlanningInput
    optimization: OptimizationProposal
    used_fallback: bool
    fallback_steps: list[str] = field(default_factory=list)
    execution_mode: Literal["langgraph", "sequential"] = "sequential"


def run_ai_orchestration(
    *,
    raw_input: str,
    planner_snapshot: str,
    plan_summary: str,
    llm_client: AIClientProtocol | None = None,
    settings: Settings | None = None,
    prefer_langgraph: bool = True,
) -> AIOrchestrationResult:
    own_client: AzureOpenAIClient | None = None
    resolved_settings = settings or get_settings()

    if llm_client is None:
        own_client = AzureOpenAIClient(settings=resolved_settings)
        llm_client = own_client

    state: dict[str, Any] = {
        "raw_input": raw_input,
        "planner_snapshot": planner_snapshot,
        "plan_summary": plan_summary,
        "parsed_input": None,
        "optimization": None,
        "evaluation": None,
        "fallback_steps": [],
        "used_fallback": False,
    }

    try:
        if prefer_langgraph and _LANGGRAPH_AVAILABLE:
            final_state = _run_with_langgraph(state, llm_client)
            mode: Literal["langgraph", "sequential"] = "langgraph"
        else:
            final_state = _run_sequential(state, llm_client)
            mode = "sequential"

        parsed_payload = final_state.get("parsed_input")
        optimization_payload = final_state.get("optimization")
        evaluation_payload = final_state.get("evaluation")
        if parsed_payload is None or optimization_payload is None or evaluation_payload is None:
            raise AIOrchestrationError("AI orchestration state is incomplete.")

        return AIOrchestrationResult(
            parsed_input=ParsedPlanningInput.model_validate(parsed_payload),
            optimization=OptimizationProposal.model_validate(optimization_payload),
            evaluation=RiskEvaluation.model_validate(evaluation_payload),
            used_fallback=bool(final_state.get("used_fallback")),
            fallback_steps=list(final_state.get("fallback_steps") or []),
            execution_mode=mode,
        )
    finally:
        if own_client is not None:
            own_client.close()


def run_ai_optimization(
    *,
    raw_input: str,
    planner_snapshot: str,
    llm_client: AIClientProtocol | None = None,
    settings: Settings | None = None,
    prefer_langgraph: bool = True,
) -> AIOptimizationResult:
    own_client: AzureOpenAIClient | None = None
    resolved_settings = settings or get_settings()

    if llm_client is None:
        own_client = AzureOpenAIClient(settings=resolved_settings)
        llm_client = own_client

    state: dict[str, Any] = {
        "raw_input": raw_input,
        "planner_snapshot": planner_snapshot,
        "parsed_input": None,
        "optimization": None,
        "fallback_steps": [],
        "used_fallback": False,
    }

    try:
        if prefer_langgraph and _LANGGRAPH_AVAILABLE:
            final_state = _run_optimization_with_langgraph(state, llm_client)
            mode: Literal["langgraph", "sequential"] = "langgraph"
        else:
            final_state = _run_optimization_sequential(state, llm_client)
            mode = "sequential"

        parsed_payload = final_state.get("parsed_input")
        optimization_payload = final_state.get("optimization")
        if parsed_payload is None or optimization_payload is None:
            raise AIOrchestrationError("AI optimization state is incomplete.")

        return AIOptimizationResult(
            parsed_input=ParsedPlanningInput.model_validate(parsed_payload),
            optimization=OptimizationProposal.model_validate(optimization_payload),
            used_fallback=bool(final_state.get("used_fallback")),
            fallback_steps=list(final_state.get("fallback_steps") or []),
            execution_mode=mode,
        )
    finally:
        if own_client is not None:
            own_client.close()


def _run_optimization_with_langgraph(
    initial_state: dict[str, Any],
    llm_client: AIClientProtocol,
) -> dict[str, Any]:
    graph: StateGraph = StateGraph(dict)
    graph.add_node("generate_input", lambda state: _generate_input_node(state, llm_client))
    graph.add_node("optimize", lambda state: _optimize_node(state, llm_client))
    graph.set_entry_point("generate_input")
    graph.add_edge("generate_input", "optimize")
    graph.add_edge("optimize", END)
    return graph.compile().invoke(initial_state)


def _run_optimization_sequential(
    state: dict[str, Any], llm_client: AIClientProtocol
) -> dict[str, Any]:
    state = _generate_input_node(state, llm_client)
    state = _optimize_node(state, llm_client)
    return state


def _run_with_langgraph(
    initial_state: dict[str, Any],
    llm_client: AIClientProtocol,
) -> dict[str, Any]:
    graph: StateGraph = StateGraph(dict)
    graph.add_node("generate_input", lambda state: _generate_input_node(state, llm_client))
    graph.add_node("optimize", lambda state: _optimize_node(state, llm_client))
    graph.add_node("evaluate", lambda state: _evaluate_node(state, llm_client))
    graph.set_entry_point("generate_input")
    graph.add_edge("generate_input", "optimize")
    graph.add_edge("optimize", "evaluate")
    graph.add_edge("evaluate", END)
    return graph.compile().invoke(initial_state)


def _run_sequential(
    state: dict[str, Any], llm_client: AIClientProtocol
) -> dict[str, Any]:
    state = _generate_input_node(state, llm_client)
    state = _optimize_node(state, llm_client)
    state = _evaluate_node(state, llm_client)
    return state


def _generate_input_node(
    state: dict[str, Any], llm_client: AIClientProtocol
) -> dict[str, Any]:
    fallback_steps = list(state.get("fallback_steps") or [])
    try:
        completion = llm_client.chat_completion(build_parsing_prompt(state["raw_input"]))
        parsed = _load_json_model(completion.content, ParsedPlanningInput)
    except Exception:
        parsed = _fallback_parsed_input(state["raw_input"])
        fallback_steps.append("generate_input")

    state["parsed_input"] = parsed.model_dump(mode="json")
    state["fallback_steps"] = fallback_steps
    state["used_fallback"] = bool(fallback_steps)
    return state


def _optimize_node(
    state: dict[str, Any], llm_client: AIClientProtocol
) -> dict[str, Any]:
    fallback_steps = list(state.get("fallback_steps") or [])
    parsed_payload = state.get("parsed_input") or {}
    planner_snapshot = state.get("planner_snapshot") or ""
    prompt_payload = json.dumps(
        {"parsed_input": parsed_payload, "planner_snapshot": planner_snapshot},
        ensure_ascii=True,
    )

    try:
        completion = llm_client.chat_completion(build_optimization_prompt(prompt_payload))
        optimization = _load_json_model(completion.content, OptimizationProposal)
    except Exception:
        parsed_input = ParsedPlanningInput.model_validate(parsed_payload)
        optimization = _fallback_optimization(parsed_input, planner_snapshot)
        fallback_steps.append("optimize")

    state["optimization"] = optimization.model_dump(mode="json")
    state["fallback_steps"] = fallback_steps
    state["used_fallback"] = bool(fallback_steps)
    return state


def _evaluate_node(
    state: dict[str, Any], llm_client: AIClientProtocol
) -> dict[str, Any]:
    fallback_steps = list(state.get("fallback_steps") or [])
    parsed_payload = state.get("parsed_input") or {}
    optimization_payload = state.get("optimization") or {}
    plan_summary = state.get("plan_summary") or ""
    prompt_payload = json.dumps(
        {
            "parsed_input": parsed_payload,
            "optimization": optimization_payload,
            "plan_summary": plan_summary,
        },
        ensure_ascii=True,
    )

    try:
        completion = llm_client.chat_completion(build_risk_explanation_prompt(prompt_payload))
        evaluation = _load_json_model(completion.content, RiskEvaluation)
    except Exception:
        parsed_input = ParsedPlanningInput.model_validate(parsed_payload)
        optimization = OptimizationProposal.model_validate(optimization_payload)
        evaluation = _fallback_evaluation(parsed_input, optimization, plan_summary)
        fallback_steps.append("evaluate")

    state["evaluation"] = evaluation.model_dump(mode="json")
    state["fallback_steps"] = fallback_steps
    state["used_fallback"] = bool(fallback_steps)
    return state


def _load_json_model(payload: str, model: type[BaseModel]) -> BaseModel:
    normalized = payload.strip()
    if normalized.startswith("```"):
        normalized = normalized.removeprefix("```json").removeprefix("```").strip()
        if normalized.endswith("```"):
            normalized = normalized[:-3].strip()

    data = json.loads(normalized)
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise AIOrchestrationError("Schema validation failed.") from exc


def _fallback_parsed_input(raw_input: str) -> ParsedPlanningInput:
    text = raw_input.strip()
    lower = text.lower()
    requirements: list[ParsedRequirement] = []
    risks: list[str] = []

    if "driver" in lower:
        requirements.append(
            ParsedRequirement(
                requirement_type="person_role_driver",
                quantity=1,
                notes="Detected from raw input keyword: driver.",
            )
        )
    if "vehicle" in lower or "transport" in lower:
        requirements.append(
            ParsedRequirement(
                requirement_type="vehicle",
                quantity=1,
                notes="Detected from raw input keyword: vehicle/transport.",
            )
        )
    if "equipment" in lower or "sound" in lower or "light" in lower:
        requirements.append(
            ParsedRequirement(
                requirement_type="equipment",
                quantity=1,
                notes="Detected from raw input keyword: equipment/sound/light.",
            )
        )
    if "delay" in lower:
        risks.append("Possible execution delay detected from operator notes.")
    if "weather" in lower:
        risks.append("Weather uncertainty may impact logistics.")

    if not requirements:
        requirements.append(
            ParsedRequirement(
                requirement_type="person_role_coordinator",
                quantity=1,
                notes="Fallback default requirement.",
            )
        )

    event_name = None
    if text:
        event_name = text.splitlines()[0].strip()[:80] or None

    return ParsedPlanningInput(
        event_name=event_name,
        requirements=requirements,
        assumptions=["Generated by fallback parser heuristic."],
        risks=risks,
    )


def _fallback_optimization(
    parsed_input: ParsedPlanningInput, planner_snapshot: str
) -> OptimizationProposal:
    requirement_count = len(parsed_input.requirements)
    changes = [
        "Prioritize critical requirements before optional staffing.",
        f"Validate availability coverage for {requirement_count} parsed requirement(s).",
    ]
    if "unassigned" in planner_snapshot.lower():
        changes.append("Add backup candidates for currently unassigned resource slots.")

    return OptimizationProposal(
        summary="Fallback optimization generated from deterministic heuristics.",
        changes=changes,
        tradeoffs=[
            "Improved coverage may increase operational cost.",
            "Additional backups reduce risk but increase coordination complexity.",
        ],
    )


def _fallback_evaluation(
    parsed_input: ParsedPlanningInput,
    optimization: OptimizationProposal,
    plan_summary: str,
) -> RiskEvaluation:
    top_risks = list(parsed_input.risks)
    if not top_risks:
        top_risks = ["Resource shortage risk due to uncertain availability."]
    if "transport" in plan_summary.lower():
        top_risks.append("Transport timing slippage risk during peak traffic.")

    overall_risk: Literal["low", "medium", "high"] = "medium"
    if len(top_risks) >= 3:
        overall_risk = "high"
    elif len(top_risks) == 1 and len(optimization.changes) <= 2:
        overall_risk = "low"

    mitigations = [
        "Confirm critical resources with T-24h and T-2h checkpoints.",
        "Keep one standby substitute for each critical role.",
    ]
    return RiskEvaluation(
        overall_risk=overall_risk,
        top_risks=top_risks,
        mitigations=mitigations,
    )
