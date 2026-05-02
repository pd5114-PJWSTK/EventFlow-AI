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

    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    openai_api_version: str = "2024-08-01-preview"
    azure_deployment_llm: str | None = None

    ai_azure_llm_enabled: bool = False
    ai_azure_llm_timeout_seconds: float = 20.0
    ai_azure_llm_max_retries: int = 2
    ai_azure_llm_retry_backoff_seconds: float = 0.5
    ai_azure_llm_rate_limit_per_minute: int = 5
    ai_azure_llm_max_input_tokens: int = 1200
    ai_azure_llm_max_output_tokens: int = 500
    ai_azure_llm_max_daily_spend_usd: float = 3.0
    ai_azure_llm_input_cost_per_1k_usd: float = 0.0004
    ai_azure_llm_output_cost_per_1k_usd: float = 0.0016

    ml_models_dir: str = "./models"
    ml_min_training_samples: int = 3
    ml_retrain_enabled: bool = True
    ml_retrain_schedule_minutes: int = 360
    ml_retrain_activation_min_samples: int = 3
    ml_retrain_activation_min_r2_improvement: float = 0.0
    ml_retrain_activation_max_mae_ratio: float = 1.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
