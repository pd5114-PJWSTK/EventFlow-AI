from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from app.services import ai_orchestration_service as orchestration


@dataclass
class _Completion:
    content: str


class _FakeClient:
    def __init__(self, payloads: list[str]) -> None:
        self._payloads = payloads
        self.calls = 0

    def chat_completion(self, *_: Any, **__: Any) -> _Completion:
        payload = self._payloads[self.calls]
        self.calls += 1
        return _Completion(content=payload)


def _parsed_json() -> str:
    return json.dumps(
        {
            "event_name": "Conference A",
            "requirements": [
                {"requirement_type": "person_role_driver", "quantity": 1},
                {"requirement_type": "vehicle", "quantity": 1},
            ],
            "assumptions": ["Venue open from 08:00."],
            "risks": ["Traffic delay risk."],
        }
    )


def _optimization_json() -> str:
    return json.dumps(
        {
            "summary": "Prefer earlier departure and reserve backup.",
            "changes": ["Start loading 30 minutes earlier."],
            "tradeoffs": ["Higher staffing overlap cost."],
        }
    )


def _evaluation_json() -> str:
    return json.dumps(
        {
            "overall_risk": "medium",
            "top_risks": ["Traffic delay risk."],
            "mitigations": ["Create alternate transport route."],
        }
    )


def test_phase5_cp02_orchestration_happy_path() -> None:
    client = _FakeClient([_parsed_json(), _optimization_json(), _evaluation_json()])
    result = orchestration.run_ai_orchestration(
        raw_input="Need one driver and one vehicle.",
        planner_snapshot="no unassigned resources",
        plan_summary="transport plan baseline",
        llm_client=client,
        prefer_langgraph=False,
    )

    assert result.used_fallback is False
    assert result.fallback_steps == []
    assert result.execution_mode == "sequential"
    assert result.parsed_input.event_name == "Conference A"
    assert result.optimization.summary.startswith("Prefer earlier departure")
    assert result.evaluation.overall_risk == "medium"
    assert client.calls == 3


def test_phase5_cp02_guardrail_fallback_on_parsing() -> None:
    client = _FakeClient(
        [
            "not-json-response",
            _optimization_json(),
            _evaluation_json(),
        ]
    )
    result = orchestration.run_ai_orchestration(
        raw_input="Driver needed for transport in bad weather.",
        planner_snapshot="snapshot",
        plan_summary="summary",
        llm_client=client,
        prefer_langgraph=False,
    )

    assert result.used_fallback is True
    assert "generate_input" in result.fallback_steps
    assert result.parsed_input.requirements


def test_phase5_cp02_guardrail_fallback_on_optimization() -> None:
    client = _FakeClient(
        [
            _parsed_json(),
            json.dumps({"bad_key": "bad_value"}),
            _evaluation_json(),
        ]
    )
    result = orchestration.run_ai_orchestration(
        raw_input="Need support crew.",
        planner_snapshot="contains unassigned slot",
        plan_summary="summary",
        llm_client=client,
        prefer_langgraph=False,
    )

    assert result.used_fallback is True
    assert "optimize" in result.fallback_steps
    assert "deterministic heuristics" in result.optimization.summary.lower()


def test_phase5_cp02_guardrail_fallback_on_evaluation() -> None:
    client = _FakeClient(
        [
            _parsed_json(),
            _optimization_json(),
            json.dumps({"overall_risk": "unknown"}),
        ]
    )
    result = orchestration.run_ai_orchestration(
        raw_input="Need support crew.",
        planner_snapshot="snapshot",
        plan_summary="Transport needed",
        llm_client=client,
        prefer_langgraph=False,
    )

    assert result.used_fallback is True
    assert "evaluate" in result.fallback_steps
    assert result.evaluation.mitigations


def test_phase5_cp02_prefers_sequential_when_langgraph_unavailable() -> None:
    client = _FakeClient([_parsed_json(), _optimization_json(), _evaluation_json()])
    result = orchestration.run_ai_orchestration(
        raw_input="raw",
        planner_snapshot="snapshot",
        plan_summary="summary",
        llm_client=client,
        prefer_langgraph=True,
    )
    assert result.execution_mode == "sequential"


def test_phase5_cp02_runs_langgraph_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    class _CompiledGraph:
        def __init__(self, nodes: dict[str, Any], edges: dict[str, str], entry: str) -> None:
            self._nodes = nodes
            self._edges = edges
            self._entry = entry

        def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
            node = self._entry
            while True:
                state = self._nodes[node](state)
                node = self._edges[node]
                if node == "__end__":
                    return state

    class _StateGraph:
        def __init__(self, _: Any) -> None:
            self.nodes: dict[str, Any] = {}
            self.edges: dict[str, str] = {}
            self.entry = ""

        def add_node(self, name: str, fn: Any) -> None:
            self.nodes[name] = fn

        def set_entry_point(self, name: str) -> None:
            self.entry = name

        def add_edge(self, source: str, target: str) -> None:
            self.edges[source] = target

        def compile(self) -> _CompiledGraph:
            return _CompiledGraph(self.nodes, self.edges, self.entry)

    monkeypatch.setattr(orchestration, "_LANGGRAPH_AVAILABLE", True)
    monkeypatch.setattr(orchestration, "StateGraph", _StateGraph)
    monkeypatch.setattr(orchestration, "END", "__end__")

    client = _FakeClient([_parsed_json(), _optimization_json(), _evaluation_json()])
    result = orchestration.run_ai_orchestration(
        raw_input="raw",
        planner_snapshot="snapshot",
        plan_summary="summary",
        llm_client=client,
        prefer_langgraph=True,
    )
    assert result.execution_mode == "langgraph"
