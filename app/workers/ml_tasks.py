from __future__ import annotations

from app.celery_app import celery_app
from app.database import SessionLocal
from app.services.ml_training_service import (
    ModelTrainingError,
    retrain_duration_model,
)


@celery_app.task(name="app.workers.ml_tasks.retrain_duration_model")
def retrain_duration_model_task() -> dict:
    db = SessionLocal()
    try:
        result = retrain_duration_model(db)
        return {
            "status": "ok",
            "model_id": result.model.model_id,
            "model_name": result.model.model_name,
            "model_version": result.model.model_version,
            "activated": result.activated,
            "decision_reason": result.decision_reason,
            "trained_samples": result.trained_samples,
            "backend": result.backend,
            "artifact_path": result.artifact_path,
            "previous_active_model_id": result.previous_active_model_id,
        }
    except ModelTrainingError as exc:
        return {"status": "error", "reason": str(exc)}
    finally:
        db.close()
