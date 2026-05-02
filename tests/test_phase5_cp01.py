from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest

from app.config import Settings
from app.services.ai_prompt_templates import (
    build_optimization_prompt,
    build_parsing_prompt,
    build_risk_explanation_prompt,
)
from app.services.azure_openai_service import (
    AzureOpenAIClient,
    AzureOpenAIUsageLimitError,
)


def _test_settings(**overrides: object) -> Settings:
    payload = {
        "ai_azure_llm_enabled": True,
        "azure_openai_endpoint": "https://example-resource.openai.azure.com",
        "azure_openai_api_key": "test-key",
        "azure_deployment_llm": "gpt-4.1-mini",
        "openai_api_version": "2024-08-01-preview",
        "ai_azure_llm_max_retries": 1,
        "ai_azure_llm_retry_backoff_seconds": 0.0,
        "ai_azure_llm_rate_limit_per_minute": 5,
        "ai_azure_llm_max_input_tokens": 1200,
        "ai_azure_llm_max_output_tokens": 300,
        "ai_azure_llm_max_daily_spend_usd": 1.0,
        "ai_azure_llm_input_cost_per_1k_usd": 0.0004,
        "ai_azure_llm_output_cost_per_1k_usd": 0.0016,
    }
    payload.update(overrides)
    return Settings(**payload)


def test_phase5_cp01_azure_client_success() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            status_code=200,
            json={
                "model": "gpt-4.1-mini",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {
                    "prompt_tokens": 120,
                    "completion_tokens": 80,
                    "total_tokens": 200,
                },
            },
        )

    client = AzureOpenAIClient(
        settings=_test_settings(),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        now_provider=lambda: datetime(2026, 5, 2, tzinfo=UTC),
        sleep_provider=lambda _: None,
    )

    completion = client.chat_completion(build_parsing_prompt("Operator note"))
    client.close()

    assert completion.content == "ok"
    assert completion.model == "gpt-4.1-mini"
    assert completion.total_tokens == 200
    assert completion.estimated_cost_usd > 0
    assert "/openai/deployments/gpt-4.1-mini/chat/completions" in str(captured["url"])
    assert "api-version=2024-08-01-preview" in str(captured["url"])
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers.get("api-key") == "test-key"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body.get("max_tokens") == 300


def test_phase5_cp01_azure_client_retries_transient_error() -> None:
    attempts = {"count": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(status_code=429, json={"error": {"message": "busy"}})
        return httpx.Response(
            status_code=200,
            json={"choices": [{"message": {"content": "retry-ok"}}], "usage": {}},
        )

    client = AzureOpenAIClient(
        settings=_test_settings(ai_azure_llm_max_retries=2),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        now_provider=lambda: datetime(2026, 5, 2, tzinfo=UTC),
        sleep_provider=lambda _: None,
    )

    completion = client.chat_completion(build_optimization_prompt("snapshot"))
    client.close()

    assert completion.content == "retry-ok"
    assert attempts["count"] == 2


def test_phase5_cp01_azure_client_rate_limit_blocks_second_call() -> None:
    attempts = {"count": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(
            status_code=200,
            json={"choices": [{"message": {"content": "ok"}}], "usage": {}},
        )

    settings = _test_settings(ai_azure_llm_rate_limit_per_minute=1)
    client = AzureOpenAIClient(
        settings=settings,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        now_provider=lambda: datetime(2026, 5, 2, tzinfo=UTC),
        time_provider=lambda: 1000.0,
        sleep_provider=lambda _: None,
    )

    first = client.chat_completion(build_risk_explanation_prompt("summary"))
    assert first.content == "ok"

    with pytest.raises(AzureOpenAIUsageLimitError):
        client.chat_completion(build_risk_explanation_prompt("summary"))
    client.close()

    assert attempts["count"] == 1


def test_phase5_cp01_azure_client_budget_limit_blocks_call() -> None:
    attempts = {"count": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(
            status_code=200,
            json={"choices": [{"message": {"content": "ok"}}], "usage": {}},
        )

    settings = _test_settings(
        ai_azure_llm_max_daily_spend_usd=0.000001,
        ai_azure_llm_max_output_tokens=300,
    )
    client = AzureOpenAIClient(
        settings=settings,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        now_provider=lambda: datetime(2026, 5, 2, tzinfo=UTC),
        sleep_provider=lambda _: None,
    )

    with pytest.raises(AzureOpenAIUsageLimitError):
        client.chat_completion(build_parsing_prompt("small text"))
    client.close()

    assert attempts["count"] == 0


def test_phase5_cp01_azure_client_input_token_cap_blocks_long_prompt() -> None:
    settings = _test_settings(ai_azure_llm_max_input_tokens=20)
    client = AzureOpenAIClient(
        settings=settings,
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(status_code=500, json={"error": "not-used"})
            )
        ),
        now_provider=lambda: datetime(2026, 5, 2, tzinfo=UTC),
        sleep_provider=lambda _: None,
    )

    with pytest.raises(AzureOpenAIUsageLimitError):
        client.chat_completion(build_parsing_prompt("x" * 500))
    client.close()


def test_phase5_cp01_prompt_templates_are_defined() -> None:
    parsing = build_parsing_prompt("manual note")
    optimization = build_optimization_prompt("planner snapshot")
    risk = build_risk_explanation_prompt("plan summary")

    assert "JSON" in parsing.system
    assert "INPUT" in parsing.user
    assert "optimization" in optimization.user.lower()
    assert "tradeoffs" in optimization.user.lower()
    assert "mitigation" in risk.user.lower()
