"""OpenAI-совместимый клиент для Qwen (DashScope) и Chutes."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    OpenAIError,
    RateLimitError,
)

from .config import Settings
from .exceptions import LLMError

logger = logging.getLogger(__name__)

_RETRYABLE = (
    RateLimitError,
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
)


@dataclass(frozen=True)
class LLMResponse:
    """Ответ модели с указанием фактического провайдера."""

    text: str
    provider: str
    model: str


class LLMClient:
    """Вызывает Qwen, при сбое — Chutes, если выбран режим auto."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def complete(self, *, system: str, user: str, temperature: float = 0.2) -> LLMResponse:
        chain = self._provider_chain()
        last_error: Exception | None = None

        logger.info("Цепочка провайдеров: %s", " → ".join(chain))
        for provider in chain:
            try:
                logger.info("Запрос к провайдеру %s", provider)
                text, model = self._complete_provider(
                    provider,
                    system=system,
                    user=user,
                    temperature=temperature,
                )
                logger.info(
                    "Ответ получен: provider=%s model=%s chars=%s",
                    provider,
                    model,
                    len(text),
                )
                return LLMResponse(text=text, provider=provider, model=model)
            except LLMError as exc:
                last_error = exc
                if provider != chain[-1]:
                    logger.warning(
                        "Провайдер %s недоступен: %s. Переключаюсь на запасной.",
                        provider,
                        exc,
                    )
                    continue
                raise

        raise LLMError("Не удалось получить ответ ни от одного LLM-провайдера.") from last_error

    def _provider_chain(self) -> list[str]:
        mode = self._settings.provider
        if mode == "qwen":
            return ["qwen"]
        if mode == "chutes":
            return ["chutes"]

        chain: list[str] = []
        if self._settings.qwen_api_key:
            chain.append("qwen")
        if self._settings.chutes_api_token:
            chain.append("chutes")
        return chain

    def _complete_provider(
        self,
        provider: str,
        *,
        system: str,
        user: str,
        temperature: float,
    ) -> tuple[str, str]:
        if provider == "qwen":
            api_key = self._settings.qwen_api_key
            base_url = self._settings.qwen_base_url
            model = self._settings.qwen_model
        else:
            api_key = self._settings.chutes_api_token
            base_url = self._settings.chutes_base_url
            model = self._settings.chutes_model

        if not api_key:
            raise LLMError(f"Для провайдера {provider} не задан ключ.")

        client = OpenAI(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            timeout=self._settings.llm_timeout,
            max_retries=0,
        )
        text = self._chat(
            client,
            model=model,
            system=system,
            user=user,
            temperature=temperature,
            label=provider,
        )
        return text, model

    def _chat(
        self,
        client: OpenAI,
        *,
        model: str,
        system: str,
        user: str,
        temperature: float,
        label: str,
    ) -> str:
        last_error: Exception | None = None
        attempts = self._settings.max_retries

        for attempt in range(1, attempts + 1):
            try:
                response = client.chat.completions.create(
                    model=model,
                    temperature=temperature,
                    max_tokens=500,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )
                content = self._extract_content(response)
                if not content:
                    raise LLMError(f"{label}: модель вернула пустой ответ.")
                return content

            except _RETRYABLE as exc:
                last_error = exc
                if attempt < attempts:
                    delay = min(2**attempt, 8)
                    logger.warning(
                        "Попытка %s/%s к %s не удалась: %s. Повтор через %s сек.",
                        attempt,
                        attempts,
                        label,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
                    continue

            except APIError as exc:
                raise LLMError(f"Ошибка API {label}: {exc}") from exc
            except OpenAIError as exc:
                raise LLMError(f"Ошибка клиента {label}: {exc}") from exc

        raise LLMError(
            f"Не удалось получить ответ от {label} после {attempts} попыток."
        ) from last_error

    @staticmethod
    def _extract_content(response: Any) -> str:
        choices = getattr(response, "choices", None) or []
        if not choices:
            return ""
        message = getattr(choices[0], "message", None)
        return (getattr(message, "content", None) or "").strip()
