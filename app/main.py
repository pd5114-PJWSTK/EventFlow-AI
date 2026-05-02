from fastapi import FastAPI

from app.api.ai_agents import router as ai_agents_router
from app.api.auth import router as auth_router
from app.api.clients import router as clients_router
from app.api.events import router as events_router
from app.api.health import router as health_router
from app.api.locations import router as locations_router
from app.api.planner import router as planner_router
from app.api.resources import router as resources_router
from app.api.test_jobs import router as test_jobs_router
from app.config import get_settings


settings = get_settings()

app = FastAPI(title=settings.app_name)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(test_jobs_router)
app.include_router(clients_router)
app.include_router(locations_router)
app.include_router(events_router)
app.include_router(resources_router)
app.include_router(planner_router)
app.include_router(ai_agents_router)
