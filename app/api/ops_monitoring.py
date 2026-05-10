from fastapi import APIRouter, Depends
from redis import Redis
from sqlalchemy import text

from app.celery_app import celery_app
from app.config import get_settings
from app.database import engine
from app.middleware.rbac import require_role
from app.schemas.ops_monitoring import OpsMonitoringResponse


router = APIRouter(
    prefix="/api/ops",
    tags=["ops-monitoring"],
    dependencies=[Depends(require_role(["admin"]))],
)


@router.get("/monitoring", response_model=OpsMonitoringResponse)
def monitoring() -> OpsMonitoringResponse:
    settings = get_settings()
    checks: dict[str, str] = {}
    queue_length: int | None = None
    workers: list[str] = []

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc.__class__.__name__}"

    if settings.ready_check_externals:
        try:
            redis = Redis.from_url(settings.redis_url)
            redis.ping()
            queue_length = int(redis.llen("celery"))
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = f"error: {exc.__class__.__name__}"
    else:
        checks["redis"] = "skipped"

    if settings.celery_always_eager:
        checks["celery"] = "eager"
        workers = ["eager-local"]
    else:
        try:
            inspector = celery_app.control.inspect(timeout=1.0)
            ping = inspector.ping() or {}
            workers = sorted(ping.keys())
            checks["celery"] = "ok" if workers else "no_workers"
        except Exception as exc:
            checks["celery"] = f"error: {exc.__class__.__name__}"

    status = "ok" if all(value in {"ok", "skipped", "eager"} for value in checks.values()) else "degraded"
    return OpsMonitoringResponse(
        status=status,
        checks=checks,
        celery_queue_length=queue_length,
        celery_workers=workers,
    )
