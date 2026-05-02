from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import sleep, time
from typing import Any, Callable

import httpx

from app.config import Settings, get_settings
from app.services.ai_prompt_templates import PromptTemplate


class AzureOpenAIError(RuntimeError):
    pass


class AzureOpenAIConfigError(AzureOpenAIError):
    pass


class AzureOpenAIUsageLimitError(AzureOpenAIError):
    pass


class AzureOpenAIResponseError(AzureOpenAIError):
    pass


@dataclass(frozen=True)
class AzureOpenAICompletion:
    content: str
    model: str | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float


class AzureOpenAIClient:
    _RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        http_client: httpx.Client | None = None,
        now_provider: Callable[[], datetime] | None = None,
        time_provider: Callable[[], float] | None = None,
        sleep_provider: Callable[[float], None] | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._now_provider = now_provider or (lambda: datetime.now(UTC))
        self._time_provider = time_provider or time
        self._sleep_provider = sleep_provider or sleep

        self._call_timestamps: deque[float] = deque()
        self._spend_day = self._now_provider().date()
        self._spent_today_usd = 0.0

        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx.Client(
            timeout=self._settings.ai_azure_llm_timeout_seconds
        )

    def close(self) -> None:
        if self._owns_http_client:
            self._http_client.close()

    def chat_completion(
        self,
        template: PromptTemplate,
        *,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
    ) -> AzureOpenAICompletion:
        self._ensure_enabled()
        self._validate_configuration()
        self._refresh_daily_spend_if_needed()
        self._enforce_rate_limit()

        output_token_limit = max_output_tokens or self._settings.ai_azure_llm_max_output_tokens
        if output_token_limit <= 0:
            raise AzureOpenAIUsageLimitError("Output token limit must be greater than 0.")
        if output_token_limit > self._settings.ai_azure_llm_max_output_tokens:
            raise AzureOpenAIUsageLimitError(
                "Output token limit exceeds configured safety cap."
            )

        messages = [
            {"role": "system", "content": template.system},
            {"role": "user", "content": template.user},
        ]
        estimated_input_tokens = self._estimate_input_tokens(messages)
        if estimated_input_tokens > self._settings.ai_azure_llm_max_input_tokens:
            raise AzureOpenAIUsageLimitError(
                "Input prompt exceeds configured token safety cap."
            )

        estimated_request_cost = self._estimate_cost_usd(
            prompt_tokens=estimated_input_tokens,
            completion_tokens=output_token_limit,
        )
        self._enforce_budget(estimated_request_cost)

        response_payload = self._perform_chat_request(
            messages=messages,
            temperature=temperature,
            max_output_tokens=output_token_limit,
        )

        usage = response_payload.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens") or estimated_input_tokens)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
        response_cost = self._estimate_cost_usd(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        self._spent_today_usd += response_cost

        choices = response_payload.get("choices") or []
        content = ""
        if choices:
            message = choices[0].get("message") or {}
            content = str(message.get("content") or "")

        return AzureOpenAICompletion(
            content=content,
            model=response_payload.get("model"),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=response_cost,
        )

    def _perform_chat_request(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        max_output_tokens: int,
    ) -> dict[str, Any]:
        url = (
            f"{self._settings.azure_openai_endpoint.rstrip('/')}"
            f"/openai/deployments/{self._settings.azure_deployment_llm}/chat/completions"
        )
        params = {"api-version": self._settings.openai_api_version}
        headers = {
            "api-key": self._settings.azure_openai_api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_output_tokens,
        }

        last_error: Exception | None = None
        attempts = self._settings.ai_azure_llm_max_retries + 1
        for attempt in range(attempts):
            try:
                response = self._http_client.post(
                    url,
                    params=params,
                    headers=headers,
                    json=payload,
                )
            except Exception as exc:
                last_error = exc
                if attempt >= attempts - 1:
                    break
                self._sleep_provider(
                    self._settings.ai_azure_llm_retry_backoff_seconds * (2**attempt)
                )
                continue

            if response.status_code in self._RETRYABLE_STATUS_CODES and attempt < attempts - 1:
                self._sleep_provider(
                    self._settings.ai_azure_llm_retry_backoff_seconds * (2**attempt)
                )
                continue

            if response.status_code >= 400:
                detail = response.text
                raise AzureOpenAIResponseError(
                    f"Azure OpenAI request failed with status {response.status_code}: {detail}"
                )

            try:
                return response.json()
            except Exception as exc:
                raise AzureOpenAIResponseError(
                    "Azure OpenAI response is not valid JSON."
                ) from exc

        raise AzureOpenAIResponseError(
            f"Azure OpenAI request failed after retries: {last_error}"
        )

    def _validate_configuration(self) -> None:
        if not self._settings.azure_openai_endpoint:
            raise AzureOpenAIConfigError("AZURE_OPENAI_ENDPOINT is not configured.")
        if not self._settings.azure_openai_api_key:
            raise AzureOpenAIConfigError("AZURE_OPENAI_API_KEY is not configured.")
        if not self._settings.azure_deployment_llm:
            raise AzureOpenAIConfigError("AZURE_DEPLOYMENT_LLM is not configured.")
        if not self._settings.openai_api_version:
            raise AzureOpenAIConfigError("OPENAI_API_VERSION is not configured.")

    def _ensure_enabled(self) -> None:
        if not self._settings.ai_azure_llm_enabled:
            raise AzureOpenAIUsageLimitError(
                "Azure LLM calls are disabled (AI_AZURE_LLM_ENABLED=false)."
            )

    def _refresh_daily_spend_if_needed(self) -> None:
        today = self._now_provider().date()
        if today != self._spend_day:
            self._spend_day = today
            self._spent_today_usd = 0.0

    def _enforce_rate_limit(self) -> None:
        now_ts = self._time_provider()
        window_start = now_ts - timedelta(minutes=1).total_seconds()
        while self._call_timestamps and self._call_timestamps[0] < window_start:
            self._call_timestamps.popleft()

        if len(self._call_timestamps) >= self._settings.ai_azure_llm_rate_limit_per_minute:
            raise AzureOpenAIUsageLimitError(
                "Rate limit exceeded for Azure LLM requests."
            )

        self._call_timestamps.append(now_ts)

    def _enforce_budget(self, estimated_request_cost: float) -> None:
        projected_total = self._spent_today_usd + estimated_request_cost
        if projected_total > self._settings.ai_azure_llm_max_daily_spend_usd:
            raise AzureOpenAIUsageLimitError(
                "Daily Azure LLM budget limit exceeded."
            )

    @staticmethod
    def _estimate_input_tokens(messages: list[dict[str, str]]) -> int:
        chars = sum(len(message.get("content", "")) for message in messages)
        return max(int(chars / 4), 1)

    def _estimate_cost_usd(self, *, prompt_tokens: int, completion_tokens: int) -> float:
        input_cost = (
            (prompt_tokens / 1000.0) * self._settings.ai_azure_llm_input_cost_per_1k_usd
        )
        output_cost = (
            (completion_tokens / 1000.0)
            * self._settings.ai_azure_llm_output_cost_per_1k_usd
        )
        return round(input_cost + output_cost, 6)
