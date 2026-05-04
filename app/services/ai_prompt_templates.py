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


def build_event_intake_prompt(raw_input: str) -> PromptTemplate:
    return PromptTemplate(
        system=(
            "You convert event intake notes into one strict JSON object for an operations database. "
            "Return valid JSON only, no markdown. Use null when unknown. Use ISO 8601 datetimes. "
            "Do not invent exact values when the text is ambiguous; leave them null so the operator can complete the sheet."
        ),
        user=(
            "Extract these keys: client_name, client_priority (low|medium|high|critical), "
            "location_name, city, location_type (conference_center|warehouse|office|outdoor|hotel|arena|other), "
            "setup_complexity_score (1-10), access_difficulty (1-5), parking_difficulty (1-5), "
            "event_name, event_type, event_subtype, attendee_count, planned_start, planned_end, "
            "event_priority (low|medium|high|critical), budget_estimate, requires_transport, "
            "requires_setup, requires_teardown, assumptions (array of strings), requirements (array). "
            "Each requirement item must contain requirement_type (person_role|equipment_type|vehicle_type), "
            "role_required (coordinator|driver|stage_manager|technician_audio|technician_light|technician_video|null), "
            "equipment_type_name (string|null), vehicle_type_required (van|truck|car|trailer|null), "
            "quantity (integer), mandatory (boolean), notes (string|null).\n\n"
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


def build_post_event_summary_prompt(raw_summary: str) -> PromptTemplate:
    return PromptTemplate(
        system=(
            "You parse post-event operational summaries into strict JSON only. "
            "Never return markdown."
        ),
        user=(
            "Extract event completion outcome details from the summary text. "
            "Return JSON with keys: finished_on_time (boolean|null), total_delay_minutes (integer|null), "
            "actual_cost (number|null), overtime_cost (number|null), transport_cost (number|null), "
            "sla_breached (boolean), client_satisfaction_score (number|null), "
            "internal_quality_score (number|null), margin_estimate (number|null), summary_notes (string). "
            "Use null where unknown.\n\n"
            f"SUMMARY:\n{raw_summary}"
        ),
    )
