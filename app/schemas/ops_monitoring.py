from pydantic import BaseModel, Field


class OpsMonitoringResponse(BaseModel):
    status: str
    checks: dict[str, str] = Field(default_factory=dict)
    celery_queue_length: int | None = None
    celery_workers: list[str] = Field(default_factory=list)
