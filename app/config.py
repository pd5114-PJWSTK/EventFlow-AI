from functools import lru_cache

from pydantic import model_validator
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

    demo_admin_username: str | None = None
    demo_admin_password: str | None = None
    demo_admin_enabled: bool = False
    auth_bootstrap_admin_username: str | None = None
    auth_bootstrap_admin_password: str | None = None
    api_test_jobs_enabled: bool = False

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
    ml_train_test_split_ratio: float = 0.2
    ml_training_random_seed: int = 42
    ml_synthetic_samples_per_real: int = 8
    ml_hardening_required_real_samples: int = 60
    ml_hardening_train_samples: int = 50
    ml_hardening_test_samples: int = 10
    ml_plan_guardrail_confidence_min: float = 0.60
    ml_plan_guardrail_ood_max: float = 0.55
    ml_plan_guardrail_high_risk_max: float = 0.70
    ml_retrain_enabled: bool = True
    ml_retrain_schedule_minutes: int = 360
    ml_retrain_activation_min_samples: int = 3
    ml_retrain_activation_min_r2_improvement: float = 0.0
    ml_retrain_activation_max_mae_ratio: float = 1.0

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        env = self.app_env.lower().strip()
        non_dev = env != "development"
        weak_secrets = {
            "dev-only-secret",
            "change-me-in-production",
            "changeme",
            "secret",
            "password",
            "admin123",
        }
        secret = self.jwt_secret_key.strip()
        if non_dev:
            if len(secret) < 32 or secret.lower() in weak_secrets:
                raise ValueError("JWT_SECRET_KEY is too weak for non-development environments.")
            if self.demo_admin_enabled:
                raise ValueError("DEMO_ADMIN_ENABLED must be false outside development.")
            if self.api_test_jobs_enabled:
                raise ValueError("API_TEST_JOBS_ENABLED must be false outside development.")
        if self.demo_admin_enabled:
            username = (self.demo_admin_username or "").strip()
            password = (self.demo_admin_password or "").strip()
            if not username or not password:
                raise ValueError("DEMO_ADMIN_USERNAME and DEMO_ADMIN_PASSWORD are required when demo auth is enabled.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
