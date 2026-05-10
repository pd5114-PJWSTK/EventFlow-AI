from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.services import runtime_incident_parser
from tests.helpers import create_event_context

def test_phase6_cp02_parse_incident_endpoint_heuristic_normalizes_to_ops_incident(
    api_client: TestClient,
) -> None:
    _, _, event_id, _, _ = create_event_context(
        api_client,
        client_name="Phase6 CP02 Parse Client",
        location_name="Phase6 CP02 Parse Venue",
        event_name="Phase6 CP02 Parse Event",
        days=20,
    )

    response = api_client.post(
        f"/api/runtime/events/{event_id}/incident/parse",
        json={
            "raw_log": (
                "CRITICAL traffic delay on highway. SLA at risk. "
                "Estimated extra cost 1800 PLN. reported by: field-coordinator."
            ),
            "prefer_llm": False,
            "author_type": "coordinator",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["event_id"] == event_id
    assert payload["incident_id"]
    assert payload["log_id"]
    assert payload["incident_type"] in {"traffic_issue", "sla_risk"}
    assert payload["severity"] == "critical"
    assert payload["sla_impact"] is True
    assert payload["parser_mode"] == "heuristic"
    assert float(payload["parse_confidence"]) > 0.0


def test_phase6_cp02_parse_incident_endpoint_uses_llm_when_available(
    api_client: TestClient, monkeypatch
) -> None:
    _, _, event_id, _, _ = create_event_context(
        api_client,
        client_name="Phase6 CP02 LLM Client",
        location_name="Phase6 CP02 LLM Venue",
        event_name="Phase6 CP02 LLM Event",
        days=21,
    )

    parsed_payload = json.dumps(
        {
            "incident_type": "equipment_failure",
            "severity": "high",
            "description": "Audio console stopped responding.",
            "root_cause": "Power module overload.",
            "sla_impact": True,
            "cost_impact": 950.5,
            "reported_by": "tech-operator-1",
        }
    )

    parsed = runtime_incident_parser._extract_payload_from_content(parsed_payload)

    def fake_parse_with_llm(*_args, **_kwargs):
        return runtime_incident_parser.IncidentParseResult(
            incident_type=parsed.incident_type,
            severity=parsed.severity,
            description=parsed.description,
            root_cause=parsed.root_cause,
            sla_impact=parsed.sla_impact,
            cost_impact=parsed.cost_impact,
            reported_by=parsed.reported_by,
            parser_mode="llm",
            parse_confidence=0.9,
        )

    monkeypatch.setattr(runtime_incident_parser, "_parse_with_llm", fake_parse_with_llm)

    response = api_client.post(
        f"/api/runtime/events/{event_id}/incident/parse",
        json={
            "raw_log": "Console is down during setup",
            "prefer_llm": True,
            "author_type": "technician",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["event_id"] == event_id
    assert payload["incident_type"] == "equipment_failure"
    assert payload["severity"] == "high"
    assert payload["parser_mode"] == "llm"
    assert payload["root_cause"] == "Power module overload."
