from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from fastapi.testclient import TestClient

from app.services.ai_orchestration_service import run_ai_optimization


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


def test_phase5_cp03_optimize_endpoint_returns_structured_payload(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        "/api/ai-agents/optimize",
        json={
            "raw_input": "Need one driver and one transport vehicle.",
            "planner_snapshot": "some planner snapshot data",
            "prefer_langgraph": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["parsed_input"]["requirements"]
    assert payload["optimization"]["summary"]
    assert payload["execution_mode"] == "sequential"
    assert payload["used_fallback"] is True
    assert "generate_input" in payload["fallback_steps"]
    assert "optimize" in payload["fallback_steps"]
    assert "evaluation" not in payload


def test_phase5_cp03_evaluate_endpoint_returns_full_payload(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        "/api/ai-agents/evaluate",
        json={
            "raw_input": "Need one driver and one transport vehicle.",
            "planner_snapshot": "unassigned slot for backup",
            "plan_summary": "Transport route includes city center",
            "prefer_langgraph": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["parsed_input"]["requirements"]
    assert payload["optimization"]["summary"]
    assert payload["evaluation"]["overall_risk"] in {"low", "medium", "high"}
    assert payload["execution_mode"] == "sequential"
    assert payload["used_fallback"] is True
    assert "generate_input" in payload["fallback_steps"]
    assert "optimize" in payload["fallback_steps"]
    assert "evaluate" in payload["fallback_steps"]


def test_phase5_cp03_optimize_service_stops_before_evaluation() -> None:
    parsed_payload = json.dumps(
        {
            "event_name": "CP03 Event",
            "requirements": [{"requirement_type": "person_role_driver", "quantity": 1}],
            "assumptions": [],
            "risks": [],
        }
    )
    optimization_payload = json.dumps(
        {
            "summary": "Use dedicated driver.",
            "changes": ["Assign primary and backup driver."],
            "tradeoffs": ["Slightly higher cost."],
        }
    )
    client = _FakeClient([parsed_payload, optimization_payload])

    result = run_ai_optimization(
        raw_input="driver required",
        planner_snapshot="snapshot",
        llm_client=client,
        prefer_langgraph=False,
    )

    assert client.calls == 2
    assert result.used_fallback is False
    assert result.optimization.summary == "Use dedicated driver."
