from app.celery_app import celery_app


@celery_app.task(name="app.workers.test_tasks.add")
def add(a: int, b: int) -> int:
    return a + b
