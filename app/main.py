from fastapi import Depends, FastAPI

from app.api.admin_users import router as admin_users_router
from app.api.ai_agents import router as ai_agents_router
from app.api.auth import router as auth_router
from app.api.clients import router as clients_router
from app.api.events import router as events_router
from app.api.health import router as health_router
from app.api.locations import router as locations_router
from app.api.ml_features import router as ml_features_router
from app.api.ml_models import router as ml_models_router
from app.api.ml_predictions import router as ml_predictions_router
from app.api.planner import router as planner_router
from app.api.resources import router as resources_router
from app.api.runtime_ops import router as runtime_ops_router
from app.api.test_jobs import router as test_jobs_router
from app.config import get_settings
from app.database import SessionLocal
from app.middleware.rbac import require_role
from app.services.auth_service import bootstrap_initial_admin, ensure_default_roles


settings = get_settings()
BUSINESS_ROLES = ["manager", "coordinator", "technician"]

app = FastAPI(title=settings.app_name)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(admin_users_router)
if settings.api_test_jobs_enabled:
    app.include_router(test_jobs_router)
app.include_router(clients_router, dependencies=[Depends(require_role(BUSINESS_ROLES))])
app.include_router(locations_router, dependencies=[Depends(require_role(BUSINESS_ROLES))])
app.include_router(events_router, dependencies=[Depends(require_role(BUSINESS_ROLES))])
app.include_router(resources_router, dependencies=[Depends(require_role(BUSINESS_ROLES))])
app.include_router(planner_router, dependencies=[Depends(require_role(BUSINESS_ROLES))])
app.include_router(ai_agents_router, dependencies=[Depends(require_role(BUSINESS_ROLES))])
app.include_router(runtime_ops_router, dependencies=[Depends(require_role(BUSINESS_ROLES))])
app.include_router(ml_features_router, dependencies=[Depends(require_role(BUSINESS_ROLES))])
app.include_router(ml_models_router, dependencies=[Depends(require_role(BUSINESS_ROLES))])
app.include_router(ml_predictions_router, dependencies=[Depends(require_role(BUSINESS_ROLES))])


@app.on_event("startup")
def init_auth_state() -> None:
    db = SessionLocal()
    try:
        ensure_default_roles(db)
        bootstrap_initial_admin(db, settings=settings)
    finally:
        db.close()
