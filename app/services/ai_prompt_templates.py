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
            "Propose improvements that reduce risk, cost, or delays."
        ),
        user=(
            "Analyze the planner snapshot and produce a concise optimization proposal. "
            "Keep the response structured with sections: summary, changes, tradeoffs.\n\n"
            f"SNAPSHOT:\n{planner_snapshot}"
        ),
    )


def build_risk_explanation_prompt(plan_summary: str) -> PromptTemplate:
    return PromptTemplate(
        system=(
            "You explain operational risk in plain language with clear mitigation actions."
        ),
        user=(
            "Explain the top execution risks in this plan and suggest mitigations. "
            "Rank risks from highest to lowest impact.\n\n"
            f"PLAN SUMMARY:\n{plan_summary}"
        ),
    )
