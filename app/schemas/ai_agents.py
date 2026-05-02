from __future__ import annotations

from pydantic import BaseModel, Field


class AIParsedRequirement(BaseModel):
    requirement_type: str
    quantity: int
    notes: str | None = None


class AIParsedInput(BaseModel):
    event_name: str | None = None
    requirements: list[AIParsedRequirement] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class AIOptimization(BaseModel):
    summary: str
    changes: list[str] = Field(default_factory=list)
    tradeoffs: list[str] = Field(default_factory=list)


class AIRiskEvaluation(BaseModel):
    overall_risk: str
    top_risks: list[str] = Field(default_factory=list)
    mitigations: list[str] = Field(default_factory=list)


class AIAgentsOptimizeRequest(BaseModel):
    raw_input: str = Field(min_length=1, max_length=6000)
    planner_snapshot: str = Field(default="", max_length=12000)
    prefer_langgraph: bool = True


class AIAgentsOptimizeResponse(BaseModel):
    parsed_input: AIParsedInput
    optimization: AIOptimization
    used_fallback: bool
    fallback_steps: list[str] = Field(default_factory=list)
    execution_mode: str


class AIAgentsEvaluateRequest(BaseModel):
    raw_input: str = Field(default="", max_length=6000)
    planner_snapshot: str = Field(default="", max_length=12000)
    plan_summary: str = Field(min_length=1, max_length=12000)
    prefer_langgraph: bool = True


class AIAgentsEvaluateResponse(BaseModel):
    parsed_input: AIParsedInput
    optimization: AIOptimization
    evaluation: AIRiskEvaluation
    used_fallback: bool
    fallback_steps: list[str] = Field(default_factory=list)
    execution_mode: str
