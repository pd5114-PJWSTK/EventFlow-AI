from celery import Celery

from app.config import get_settings


settings = get_settings()

celery_app = Celery("eventflow", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_default_queue="eventflow",
    task_always_eager=settings.celery_always_eager,
    task_eager_propagates=True,
    imports=("app.workers.test_tasks", "app.workers.runtime_tasks"),
)

