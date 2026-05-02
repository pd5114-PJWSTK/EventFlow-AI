from celery import Celery
from datetime import timedelta

from app.config import get_settings


settings = get_settings()

celery_app = Celery("eventflow", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_default_queue="eventflow",
    task_always_eager=settings.celery_always_eager,
    task_eager_propagates=True,
    imports=("app.workers.test_tasks", "app.workers.runtime_tasks", "app.workers.ml_tasks"),
)

if settings.ml_retrain_enabled:
    celery_app.conf.beat_schedule = {
        "ml-retrain-duration-model": {
            "task": "app.workers.ml_tasks.retrain_duration_model",
            "schedule": timedelta(minutes=settings.ml_retrain_schedule_minutes),
        }
    }

