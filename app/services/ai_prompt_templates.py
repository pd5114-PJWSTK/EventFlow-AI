from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptTemplate:
    system: str
    user: str


def build_parsing_prompt(raw_input: str) -> PromptTemplate:
    return PromptTemplate(
        system=(
            "You parse operational planning notes into strict JSON. "
            "Return valid JSON only, no markdown."
        ),
        user=(
            "Extract event planning entities from the following text. "
            "Include requirements, timing, risks, and assumptions.\n\n"
            f"INPUT:\n{raw_input}"
        ),
    )


def build_optimization_prompt(planner_snapshot: str) -> PromptTemplate:
    return PromptTemplate(
        system=(
            "You are an optimization assistant for event planning. "
            "Propose improvements that reduce risk, cost, or delays. "
            "Return strict JSON only."
        ),
        user=(
            "Analyze the planner snapshot and return JSON optimization proposal with keys: "
            "summary (string), changes (array of strings), tradeoffs (array of strings).\n\n"
            f"SNAPSHOT:\n{planner_snapshot}"
        ),
    )


def build_risk_explanation_prompt(plan_summary: str) -> PromptTemplate:
    return PromptTemplate(
        system=(
            "You explain operational risk in plain language with clear mitigation actions. "
            "Return strict JSON only."
        ),
        user=(
            "Return JSON with keys: overall_risk (low|medium|high), "
            "top_risks (array of strings), mitigations (array of strings). "
            "Rank top_risks from highest to lowest impact.\n\n"
            f"PLAN SUMMARY:\n{plan_summary}"
        ),
    )


def build_incident_parsing_prompt(raw_log: str) -> PromptTemplate:
    return PromptTemplate(
        system=(
            "You parse operator runtime incident notes into strict JSON only. "
            "Never return markdown."
        ),
        user=(
            "Extract and normalize incident details from the log text. "
            "Return JSON with keys: incident_type "
            "(delay|equipment_failure|staff_absence|traffic_issue|weather_issue|"
            "client_change_request|venue_access_issue|sla_risk|safety_issue|other), "
            "severity (low|medium|high|critical), description (string), "
            "root_cause (string|null), sla_impact (boolean), cost_impact (number|null), "
            "reported_by (string|null).\n\n"
            f"LOG:\n{raw_log}"
        ),
    )
