from __future__ import annotations

import os
import sys


WEAK_JWT_VALUES = {
    "",
    "dev-only-secret",
    "change-me-in-production",
    "changeme",
    "secret",
    "password",
    "admin123",
}


def _is_true(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    app_env = (os.getenv("APP_ENV") or "development").strip().lower()
    jwt_secret = (os.getenv("JWT_SECRET_KEY") or "").strip()
    demo_admin_enabled = _is_true(os.getenv("DEMO_ADMIN_ENABLED"))
    test_jobs_enabled = _is_true(os.getenv("API_TEST_JOBS_ENABLED"))
    api_docs_enabled = _is_true(os.getenv("API_DOCS_ENABLED"))

    errors: list[str] = []
    if app_env == "development":
        errors.append("APP_ENV cannot be development for production deployment.")
    if len(jwt_secret) < 32 or jwt_secret.lower() in WEAK_JWT_VALUES:
        errors.append("JWT_SECRET_KEY is missing/weak for production deployment.")
    if demo_admin_enabled:
        errors.append("DEMO_ADMIN_ENABLED must be false in production.")
    if test_jobs_enabled:
        errors.append("API_TEST_JOBS_ENABLED must be false in production.")
    if api_docs_enabled:
        errors.append("API_DOCS_ENABLED must be false in production.")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("OK: production env checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

