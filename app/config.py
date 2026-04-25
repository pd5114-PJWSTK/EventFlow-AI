from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "EventFlow API"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    database_url: str = "sqlite+pysqlite:///./eventflow.db"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret_key: str = "dev-only-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 24 * 60

    demo_admin_username: str = "admin"
    demo_admin_password: str = "admin123"

    ready_check_externals: bool = False
    celery_always_eager: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
