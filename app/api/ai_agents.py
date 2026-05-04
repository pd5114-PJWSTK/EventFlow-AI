from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.rbac import get_current_auth_payload
from app.schemas.ai_agents import (
    AIAgentsIngestEventCommitRequest,
    AIAgentsIngestEventPreviewRequest,
    AIAgentsIngestEventPreviewResponse,
    AIAgentsEvaluateRequest,
    AIAgentsEvaluateResponse,
    AIAgentsIngestEventRequest,
    AIAgentsIngestEventResponse,
    AIAgentsOptimizeRequest,
    AIAgentsOptimizeResponse,
)
from app.services.ai_event_ingest_service import AIEventIngestError, ingest_event_from_text
from app.services.ai_event_ingest_service import commit_ingest_event_draft, preview_ingest_event_from_text
from app.services.ai_orchestration_service import (
    AIOrchestrationError,
    run_ai_optimization,
    run_ai_orchestration,
)
from app.config import get_settings


router = APIRouter(prefix="/api/ai-agents", tags=["ai-agents"])


@router.get("/llm-status")
def llm_status_endpoint() -> dict[str, str | bool | None]:
    settings = get_settings()
    endpoint_configured = bool(settings.azure_openai_endpoint)
    api_key_configured = bool(settings.azure_openai_api_key)
    deployment_configured = bool(settings.azure_deployment_llm)
    configured = endpoint_configured and api_key_configured and deployment_configured
    llm_ready = settings.ai_azure_llm_enabled and configured
    if llm_ready:
        message = "LLM is enabled and configured."
    elif not settings.ai_azure_llm_enabled:
        message = "LLM is disabled by AI_AZURE_LLM_ENABLED=false; parsers use fallback mode."
    else:
        message = "LLM is enabled, but Azure OpenAI configuration is incomplete."
    return {
        "enabled": settings.ai_azure_llm_enabled,
        "configured": configured,
        "endpoint_configured": endpoint_configured,
        "api_key_configured": api_key_configured,
        "deployment_configured": deployment_configured,
        "deployment": settings.azure_deployment_llm,
        "mode": "llm" if llm_ready else "fallback",
        "message": message,
    }


@router.post("/optimize", response_model=AIAgentsOptimizeResponse)
def optimize_endpoint(payload: AIAgentsOptimizeRequest) -> AIAgentsOptimizeResponse:
    try:
        result = run_ai_optimization(
            raw_input=payload.raw_input,
            planner_snapshot=payload.planner_snapshot,
            prefer_langgraph=payload.prefer_langgraph,
        )
    except AIOrchestrationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return AIAgentsOptimizeResponse(
        parsed_input=result.parsed_input.model_dump(mode="json"),
        optimization=result.optimization.model_dump(mode="json"),
        used_fallback=result.used_fallback,
        fallback_steps=result.fallback_steps,
        execution_mode=result.execution_mode,
    )


@router.post("/evaluate", response_model=AIAgentsEvaluateResponse)
def evaluate_endpoint(payload: AIAgentsEvaluateRequest) -> AIAgentsEvaluateResponse:
    try:
        result = run_ai_orchestration(
            raw_input=payload.raw_input,
            planner_snapshot=payload.planner_snapshot,
            plan_summary=payload.plan_summary,
            prefer_langgraph=payload.prefer_langgraph,
        )
    except AIOrchestrationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return AIAgentsEvaluateResponse(
        parsed_input=result.parsed_input.model_dump(mode="json"),
        optimization=result.optimization.model_dump(mode="json"),
        evaluation=result.evaluation.model_dump(mode="json"),
        used_fallback=result.used_fallback,
        fallback_steps=result.fallback_steps,
        execution_mode=result.execution_mode,
    )


@router.post("/ingest-event", response_model=AIAgentsIngestEventResponse)
def ingest_event_endpoint(
    payload: AIAgentsIngestEventRequest,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_auth_payload),
) -> AIAgentsIngestEventResponse:
    try:
        return ingest_event_from_text(
            db,
            raw_input=payload.raw_input,
            initiated_by=payload.initiated_by or str(auth_payload.get("username", "")),
            initiated_by_user_id=str(auth_payload.get("sub", "")),
            prefer_langgraph=payload.prefer_langgraph,
        )
    except AIEventIngestError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/ingest-event/preview", response_model=AIAgentsIngestEventPreviewResponse)
def ingest_event_preview_endpoint(
    payload: AIAgentsIngestEventPreviewRequest,
    auth_payload: dict = Depends(get_current_auth_payload),
) -> AIAgentsIngestEventPreviewResponse:
    try:
        return preview_ingest_event_from_text(
            raw_input=payload.raw_input,
            initiated_by=payload.initiated_by or str(auth_payload.get("username", "")),
            prefer_langgraph=payload.prefer_langgraph,
        )
    except AIEventIngestError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/ingest-event/commit", response_model=AIAgentsIngestEventResponse)
def ingest_event_commit_endpoint(
    payload: AIAgentsIngestEventCommitRequest,
    db: Session = Depends(get_db),
    auth_payload: dict = Depends(get_current_auth_payload),
) -> AIAgentsIngestEventResponse:
    try:
        return commit_ingest_event_draft(
            db,
            payload=AIAgentsIngestEventCommitRequest(
                draft=payload.draft,
                assumptions=payload.assumptions,
                parser_mode=payload.parser_mode,
                used_fallback=payload.used_fallback,
                initiated_by=payload.initiated_by or str(auth_payload.get("username", "")),
            ),
            initiated_by_user_id=str(auth_payload.get("sub", "")),
        )
    except AIEventIngestError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
