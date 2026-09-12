"""Основной агент для анализа сайтов и генерации резюме."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from .config import Settings, get_settings
from .exceptions import ValidationError
from .extractor import extract_main_text, fetch_page_html
from .llm import LLMClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Ты аналитик веб-контента. "
    "Твоя задача — делать точные, нейтральные и фактические резюме страниц. "
    "Не выдумывай факты, не добавляй оценки и не используй списки. "
    "Если информации мало, опирайся только на предоставленный текст. "
    "Ответ должен быть на языке исходного текста и состоять из 3–5 предложений. "
    "Возвращай только текст резюме, без заголовков, пояснений и кавычек."
)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")
_LEADING_LABEL_RE = re.compile(
    r"^(Резюме|Суть|Краткое содержание|Сайт рассказывает)[:\s-]+",
    re.IGNORECASE,
)


def split_sentences(text: str) -> list[str]:
    """Разбивает текст на предложения."""
    cleaned = text.strip()
    if not cleaned:
        return []
    parts = _SENTENCE_SPLIT_RE.split(cleaned)
    return [part.strip() for part in parts if part.strip()]


@dataclass(frozen=True)
class SummaryResult:
    """Результат работы агента."""

    url: str
    summary: str
    provider: str
    model: str
    sentences_count: int
    source_chars: int

    def __str__(self) -> str:
        return self.summary


class PageSummarizerAgent:
    """Агент для формирования краткого резюме сайта по URL."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._llm = LLMClient(self._settings)

    def summarize_url(self, url: str) -> SummaryResult:
        """Полный цикл: загрузка, извлечение текста, суммаризация."""
        normalized_url = url.strip()
        logger.info("Загружаю страницу: %s", normalized_url)

        html = fetch_page_html(
            normalized_url,
            timeout=self._settings.request_timeout,
            max_retries=self._settings.max_retries,
            user_agent=self._settings.user_agent,
        )
        text = extract_main_text(html, url=normalized_url)
        truncated_text = self._truncate_text(text, self._settings.max_input_chars)

        if len(truncated_text) < len(text):
            logger.info(
                "Текст обрезан с %s до %s символов перед отправкой в модель.",
                len(text),
                len(truncated_text),
            )
        logger.info(
            "Передаю текст модели. Длина исходного текста: %s символов.",
            len(text),
        )
        logger.debug("Начало извлечённого текста: %s", text[:240])

        summary, provider, model = self._summarize_with_validation(
            truncated_text,
            normalized_url,
        )
        sentences = split_sentences(summary)
        logger.info(
            "Резюме готово: provider=%s model=%s sentences=%s",
            provider,
            model,
            len(sentences),
        )

        return SummaryResult(
            url=normalized_url,
            summary=summary,
            provider=provider,
            model=model,
            sentences_count=len(sentences),
            source_chars=len(text),
        )

    def _truncate_text(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "…"

    def _summarize_with_validation(self, text: str, url: str) -> tuple[str, str, str]:
        first_prompt = self._build_user_prompt(text, url, emphasize_length=False)
        first_raw = self._llm.complete(system=SYSTEM_PROMPT, user=first_prompt)
        first_summary = self._enforce_max_sentences(self._clean_summary(first_raw.text))

        if len(split_sentences(first_summary)) >= 3:
            return first_summary, first_raw.provider, first_raw.model

        logger.info("Первый ответ содержит меньше 3 предложений. Повторяю запрос.")

        second_prompt = self._build_user_prompt(text, url, emphasize_length=True)
        second_raw = self._llm.complete(system=SYSTEM_PROMPT, user=second_prompt)
        second_summary = self._enforce_max_sentences(self._clean_summary(second_raw.text))

        if len(split_sentences(second_summary)) >= 3:
            return second_summary, second_raw.provider, second_raw.model

        fallback = self._fallback_extractive_summary(text)
        if fallback:
            logger.warning(
                "Модель не выдала 3–5 предложений. "
                "Использую запасной извлекательный вариант."
            )
            return self._enforce_max_sentences(fallback), second_raw.provider, second_raw.model

        best = (
            second_summary
            if len(split_sentences(second_summary)) >= len(split_sentences(first_summary))
            else first_summary
        )
        if len(split_sentences(best)) < 3:
            raise ValidationError(
                "Не удалось сформировать резюме из 3–5 предложений. "
                "Возможно, на странице слишком мало контента."
            )
        return self._enforce_max_sentences(best), second_raw.provider, second_raw.model

    def _build_user_prompt(self, text: str, url: str, *, emphasize_length: bool) -> str:
        emphasis = (
            "\nОчень важно: ответ должен содержать ровно 3–5 предложений."
            if emphasize_length
            else ""
        )
        return (
            f"URL: {url}\n"
            f"Текст страницы:\n\"\"\"\n{text}\n\"\"\"\n\n"
            "Сформулируй краткое резюме содержания сайта в 3–5 предложениях. "
            "Передай ключевые мысли без воды, оценок и домыслов. "
            "Не начинай ответ с фраз вроде 'Этот сайт...', "
            "'Статья рассказывает...' или 'Резюме:'. "
            "Верни только текст резюме, без списков и пояснений."
            + emphasis
        )

    def _clean_summary(self, raw: str) -> str:
        cleaned = raw.strip()

        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z0-9]*\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        if cleaned.startswith("{") and cleaned.endswith("}"):
            try:
                payload = json.loads(cleaned)
                if isinstance(payload, dict):
                    for key in ("summary", "result", "text", "content"):
                        value = payload.get(key)
                        if isinstance(value, str) and value.strip():
                            cleaned = value.strip()
                            break
            except json.JSONDecodeError:
                pass

        cleaned = cleaned.replace("\n", " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = _LEADING_LABEL_RE.sub("", cleaned).strip()
        return cleaned

    def _enforce_max_sentences(self, summary: str, max_sentences: int = 5) -> str:
        sentences = split_sentences(summary)
        if len(sentences) <= max_sentences:
            return summary
        return " ".join(sentences[:max_sentences])

    def _fallback_extractive_summary(
        self,
        text: str,
        min_sentences: int = 3,
        max_sentences: int = 5,
    ) -> str | None:
        sentences = split_sentences(text)
        if len(sentences) < min_sentences:
            return None
        return " ".join(sentences[:max_sentences])


def run_agent(url: str) -> SummaryResult:
    """Быстрый запуск агента без ручной инициализации."""
    agent = PageSummarizerAgent()
    return agent.summarize_url(url)
