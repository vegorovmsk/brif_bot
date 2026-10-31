"""LLMClient и OpenAICompatibleLLM: один клиент на любого провайдера с API OpenAI (ADR-04)."""

import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx2
from openai import AsyncOpenAI

# Повторы сетевых ошибок, таймаутов, 429 и 5xx делает сам SDK (ADR-05: tenacity не нужна).
SDK_MAX_RETRIES = 2


@dataclass(frozen=True)
class LLMResult:
    """Ответ модели и учёт: текст JSON, токены, задержка."""

    text: str
    prompt_tokens: int
    completion_tokens: int
    model: str
    latency_ms: int


class LLMClient(Protocol):
    """Один запрос к модели со структурированным ответом по JSON-схеме (ADR-05)."""

    provider: str
    model: str

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        schema_name: str,
        schema: dict[str, Any],
        temperature: float,
        max_tokens: int,
        timeout_s: float,
    ) -> LLMResult:
        """Выполнить запрос; сетевые и API-ошибки пробрасываются как исключения openai."""
        ...


class OpenAICompatibleLLM:
    """Клиент OpenAI-совместимого API: YandexGPT в Yandex AI Studio, OpenRouter и др."""

    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        api_key: str,
        model: str,
        project: str | None = None,
        proxy: str | None = None,
        http_client: httpx2.AsyncClient | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        if http_client is None and proxy:
            http_client = httpx2.AsyncClient(proxy=proxy)
        self._client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            project=project or None,
            max_retries=SDK_MAX_RETRIES,
            http_client=http_client,
        )

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        schema_name: str,
        schema: dict[str, Any],
        temperature: float,
        max_tokens: int,
        timeout_s: float,
    ) -> LLMResult:
        started = time.monotonic()
        response_format: Any = {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "schema": schema},
        }
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout_s,
            response_format=response_format,
        )
        usage = response.usage
        return LLMResult(
            text=response.choices[0].message.content or "",
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            model=self.model,
            latency_ms=int((time.monotonic() - started) * 1000),
        )
