from __future__ import annotations

import os
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.services.auth_service import create_user, ensure_default_roles


@pytest.fixture
def api_client() -> Generator[TestClient, None, None]:
    os.environ["READY_CHECK_EXTERNALS"] = "false"
    os.environ["CELERY_ALWAYS_EAGER"] = "true"
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import app
    app.router.on_startup.clear()

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {"core": None, "ai": None, "ops": None, "auth": None}},
        future=True,
    )
    testing_session_local = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, future=True
    )

    Base.metadata.create_all(bind=engine)

    seed_db = testing_session_local()
    try:
        ensure_default_roles(seed_db)
        create_user(
            seed_db,
            username="test-admin",
            password="StrongPass!234",
            role_names=["admin", "manager", "coordinator", "technician"],
            is_superadmin=True,
        )
    finally:
        seed_db.close()

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        login_response = client.post(
            "/auth/login",
            json={"username": "test-admin", "password": "StrongPass!234"},
        )
        assert login_response.status_code == 200
        tokens = login_response.json()
        client.headers.update({"Authorization": f"Bearer {tokens['access_token']}"})
        yield client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
