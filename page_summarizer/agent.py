"""Основной агент для разбора судебных актов."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from .config import Settings, get_settings
from .exceptions import ExtractionError, ValidationError
from .extractor import (
    extract_from_bytes,
    extract_from_file,
    extract_main_text,
    fetch_page_html,
    normalize_text,
)
from .llm import LLMClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Ты юрист-аналитик судебных актов. "
    "Разбираешь только предоставленный текст: не выдумывай реквизиты, стороны, "
    "резолютив и нормы. Если поля нет в тексте, укажи «не указано». "
    "Ответ верни только валидным JSON без markdown, без пояснений и без обёртки. "
    "Ключи JSON: court, case_number, parties, operative_part, norms, summary. "
    "summary — нейтральное резюме акта из 3–5 предложений на языке исходного текста, "
    "без списков, заголовков и вводных вроде «Резюме:»."
)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")
_LEADING_LABEL_RE = re.compile(
    r"^(Резюме|Суть|Краткое содержание|Сайт рассказывает)[:\s-]+",
    re.IGNORECASE,
)
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)

_ANALYSIS_KEYS = (
    "court",
    "case_number",
    "parties",
    "operative_part",
    "norms",
    "summary",
)


def split_sentences(text: str) -> list[str]:
    """Разбивает текст на предложения."""
    cleaned = text.strip()
    if not cleaned:
        return []
    parts = _SENTENCE_SPLIT_RE.split(cleaned)
    return [part.strip() for part in parts if part.strip()]


@dataclass(frozen=True)
class AnalysisResult:
    """Структурированный разбор судебного акта."""

    source: str
    court: str
    case_number: str
    parties: str
    operative_part: str
    norms: str
    summary: str
    provider: str
    model: str
    sentences_count: int
    source_chars: int

    def __str__(self) -> str:
        return self.format_text()

    def format_text(self) -> str:
        """Человекочитаемый разбор для CLI и простого вывода."""
        return (
            f"Суд: {self.court}\n"
            f"Дело: {self.case_number}\n"
            f"Стороны: {self.parties}\n"
            f"Резолютив: {self.operative_part}\n"
            f"Нормы: {self.norms}\n\n"
            f"{self.summary}"
        )


SummaryResult = AnalysisResult


class PageSummarizerAgent:
    """Агент разбора судебного акта: файл, текст или URL опубликованного акта."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._llm = LLMClient(self._settings)

    def summarize_url(self, url: str) -> AnalysisResult:
        """Совместимость: разбор акта, опубликованного по URL."""
        return self.analyze(url=url)

    def analyze(
        self,
        *,
        url: str = "",
        text: str = "",
        file_path: str = "",
        file_bytes: bytes | None = None,
        filename: str = "",
    ) -> AnalysisResult:
        """Полный цикл: извлечение текста акта и структурированный разбор."""
        source, extracted = self._load_source_text(
            url=url,
            text=text,
            file_path=file_path,
            file_bytes=file_bytes,
            filename=filename,
        )
        truncated_text = self._truncate_text(extracted, self._settings.max_input_chars)

        if len(truncated_text) < len(extracted):
            logger.info(
                "Текст обрезан с %s до %s символов перед отправкой в модель.",
                len(extracted),
                len(truncated_text),
            )
        logger.info(
            "Передаю текст модели. Длина исходного текста: %s символов.",
            len(extracted),
        )
        logger.debug("Начало извлечённого текста: %s", extracted[:240])

        parsed, provider, model = self._analyze_with_validation(
            truncated_text,
            source,
        )
        summary = parsed["summary"]
        sentences = split_sentences(summary)
        logger.info(
            "Разбор готов: provider=%s model=%s sentences=%s",
            provider,
            model,
            len(sentences),
        )

        return AnalysisResult(
            source=source,
            court=parsed["court"],
            case_number=parsed["case_number"],
            parties=parsed["parties"],
            operative_part=parsed["operative_part"],
            norms=parsed["norms"],
            summary=summary,
            provider=provider,
            model=model,
            sentences_count=len(sentences),
            source_chars=len(extracted),
        )

    def _load_source_text(
        self,
        *,
        url: str,
        text: str,
        file_path: str,
        file_bytes: bytes | None,
        filename: str,
    ) -> tuple[str, str]:
        if file_bytes:
            label = filename.strip() or "загруженный файл"
            logger.info("Извлекаю текст из файла: %s", label)
            return label, extract_from_bytes(file_bytes, filename=label)

        path_value = file_path.strip()
        if path_value:
            path = Path(path_value)
            logger.info("Извлекаю текст из файла: %s", path)
            return str(path), extract_from_file(path)

        pasted = normalize_text(text)
        if pasted:
            logger.info("Анализирую вставленный текст судебного акта")
            if len(pasted) < 180:
                raise ExtractionError(
                    "Вставленного текста слишком мало для анализа судебного акта."
                )
            return "вставленный текст", pasted

        normalized_url = url.strip()
        if normalized_url:
            logger.info("Загружаю опубликованный акт: %s", normalized_url)
            html = fetch_page_html(
                normalized_url,
                timeout=self._settings.request_timeout,
                max_retries=self._settings.max_retries,
                user_agent=self._settings.user_agent,
            )
            return normalized_url, extract_main_text(html, url=normalized_url)

        raise ValidationError(
            "Укажите судебный акт: файл PDF/DOCX/TXT, текст или ссылку на публикацию."
        )

    def _truncate_text(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "…"

    def _analyze_with_validation(self, text: str, source: str) -> tuple[dict[str, str], str, str]:
        first_prompt = self._build_user_prompt(text, source, emphasize_length=False)
        first_raw = self._llm.complete(
            system=SYSTEM_PROMPT,
            user=first_prompt,
            max_tokens=1600,
        )
        first_parsed = self._parse_analysis(first_raw.text)

        if self._is_complete(first_parsed):
            return first_parsed, first_raw.provider, first_raw.model

        logger.info("Первый ответ неполный. Повторяю запрос.")

        second_prompt = self._build_user_prompt(text, source, emphasize_length=True)
        second_raw = self._llm.complete(
            system=SYSTEM_PROMPT,
            user=second_prompt,
            max_tokens=1600,
        )
        second_parsed = self._parse_analysis(second_raw.text)

        if self._is_complete(second_parsed):
            return second_parsed, second_raw.provider, second_raw.model

        fallback_summary = self._fallback_extractive_summary(text)
        if fallback_summary:
            logger.warning(
                "Модель не выдала полный JSON-разбор. "
                "Заполняю резюме запасным извлекательным вариантом."
            )
            merged = self._empty_fields()
            merged.update({k: v for k, v in second_parsed.items() if v != "не указано"})
            merged["summary"] = self._enforce_max_sentences(fallback_summary)
            return merged, second_raw.provider, second_raw.model

        if self._has_any_field(second_parsed) or self._has_any_field(first_parsed):
            best = second_parsed if self._score(second_parsed) >= self._score(first_parsed) else first_parsed
            return best, second_raw.provider, second_raw.model

        raise ValidationError(
            "Не удалось разобрать судебный акт. "
            "Проверьте, что в файле есть текстовый слой, а не только скан."
        )

    def _build_user_prompt(self, text: str, source: str, *, emphasize_length: bool) -> str:
        emphasis = (
            "\nОчень важно: верни только JSON и поле summary из ровно 3–5 предложений."
            if emphasize_length
            else ""
        )
        return (
            f"Источник: {source}\n"
            f"Текст судебного акта:\n\"\"\"\n{text}\n\"\"\"\n\n"
            "Извлеки структурированный разбор: суд, номер дела, стороны, "
            "резолютивную часть и применённые нормы. "
            "Не выдумывай факты. Поле summary — 3–5 предложений по содержанию акта. "
            "Верни только JSON."
            + emphasis
        )

    def _parse_analysis(self, raw: str) -> dict[str, str]:
        payload = self._extract_json_object(raw)
        result = self._empty_fields()
        if not payload:
            cleaned = self._clean_summary(raw)
            if cleaned:
                result["summary"] = self._enforce_max_sentences(cleaned)
            return result

        for key in _ANALYSIS_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                value = "; ".join(str(item).strip() for item in value if str(item).strip())
            if isinstance(value, str) and value.strip():
                cleaned = value.strip()
                if key == "summary":
                    cleaned = self._clean_summary(cleaned)
                    cleaned = self._enforce_max_sentences(cleaned)
                result[key] = cleaned
        return result

    def _extract_json_object(self, raw: str) -> dict | None:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z0-9]*\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned).strip()
        try:
            payload = json.loads(cleaned)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass
        match = _JSON_OBJECT_RE.search(cleaned)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def _empty_fields(self) -> dict[str, str]:
        return {key: "не указано" for key in _ANALYSIS_KEYS}

    def _is_complete(self, parsed: dict[str, str]) -> bool:
        if parsed.get("summary", "не указано") == "не указано":
            return False
        return len(split_sentences(parsed["summary"])) >= 3

    def _has_any_field(self, parsed: dict[str, str]) -> bool:
        return any(parsed.get(key, "не указано") != "не указано" for key in _ANALYSIS_KEYS)

    def _score(self, parsed: dict[str, str]) -> int:
        filled = sum(1 for key in _ANALYSIS_KEYS if parsed.get(key, "не указано") != "не указано")
        return filled * 10 + len(split_sentences(parsed.get("summary", "")))

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


def run_agent(
    source: str | None = None,
    *,
    url: str = "",
    text: str = "",
    file_path: str = "",
) -> AnalysisResult:
    """Быстрый запуск агента без ручной инициализации."""
    agent = PageSummarizerAgent()
    if source:
        stripped = source.strip()
        if stripped.lower().startswith(("http://", "https://")):
            url = stripped
        elif Path(stripped).is_file() or Path(stripped).suffix.lower() in {
            ".pdf",
            ".docx",
            ".txt",
            ".md",
        }:
            file_path = stripped
        else:
            text = stripped
    return agent.analyze(url=url, text=text, file_path=file_path)
