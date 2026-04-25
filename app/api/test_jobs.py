from fastapi import APIRouter
from pydantic import BaseModel

from app.celery_app import celery_app
from app.workers.test_tasks import add


router = APIRouter(prefix="/api/test", tags=["jobs"])


class AddJobPayload(BaseModel):
    a: int
    b: int


@router.post("/async-job")
def queue_add_job(payload: AddJobPayload) -> dict[str, str | int]:
    result = add.delay(payload.a, payload.b)
    response: dict[str, str | int] = {"task_id": result.id, "status": result.status}
    if result.ready():
        response["result"] = int(result.result)
    return response


@router.get("/async-job/{task_id}")
def get_job_status(task_id: str) -> dict[str, str | int | None]:
    result = celery_app.AsyncResult(task_id)
    payload: dict[str, str | int | None] = {
        "task_id": task_id,
        "status": result.status,
    }
    if result.ready():
        try:
            res = result.result
            if isinstance(res, (int, float, str)):
                payload["result"] = int(res)
            else:
                payload["result"] = None
                payload["note"] = "result-not-serializable"
        except Exception as exc:  # guards NotRegistered and others
            payload["result"] = None
            payload["note"] = f"error: {exc.__class__.__name__}"
    return payload
