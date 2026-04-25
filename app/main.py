from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.test_jobs import router as test_jobs_router
from app.config import get_settings


settings = get_settings()

app = FastAPI(title=settings.app_name)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(test_jobs_router)
