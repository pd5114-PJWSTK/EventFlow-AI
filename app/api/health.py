from fastapi import APIRouter, HTTPException
from redis import Redis
from sqlalchemy import text

from app.config import get_settings
from app.database import engine
from app.schemas.health import HealthResponse, ReadyResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadyResponse)
def ready() -> ReadyResponse:
    settings = get_settings()

    if not settings.ready_check_externals:
        return ReadyResponse(status="ok", checks={"database": "skipped", "redis": "skipped"})

    checks: dict[str, str] = {}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc.__class__.__name__}"

    try:
        redis = Redis.from_url(settings.redis_url)
        redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc.__class__.__name__}"

    if all(value == "ok" for value in checks.values()):
        return ReadyResponse(status="ok", checks=checks)

    raise HTTPException(status_code=503, detail={"status": "not_ready", "checks": checks})
