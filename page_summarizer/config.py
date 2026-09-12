"""Конфигурация приложения и чтение переменных окружения."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from .exceptions import ConfigError

_PROJECT_ROOT = Path(__file__).resolve().parents[1]

_FALLBACK_ENV = (
    Path.home()
    / "Desktop"
    / "Курс нейросети для юристов (материалы)"
    / "создание бота-ИИ ассистента"
    / ".env"
)

_ALLOWED_PROVIDERS = {"auto", "qwen", "chutes"}


@dataclass(frozen=True)
class Settings:
    """Настройки агента."""

    provider: str
    qwen_api_key: str
    qwen_base_url: str
    qwen_model: str
    chutes_api_token: str
    chutes_base_url: str
    chutes_model: str
    request_timeout: float
    llm_timeout: float
    max_retries: int
    max_input_chars: int
    user_agent: str


def load_environment() -> None:
    """Загружает .env проекта, затем запасной .env с уже настроенными ключами."""
    load_dotenv(_PROJECT_ROOT / ".env", override=False)
    if _FALLBACK_ENV.is_file():
        load_dotenv(_FALLBACK_ENV, override=False)


def _first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw.strip())
    except ValueError as exc:
        raise ConfigError(f"Переменная {name} должна быть числом.") from exc


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw.strip())
    except ValueError as exc:
        raise ConfigError(f"Переменная {name} должна быть целым числом.") from exc
    if value <= 0:
        raise ConfigError(f"Переменная {name} должна быть больше нуля.")
    return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Возвращает настройки приложения из переменных окружения."""
    load_environment()

    provider = _first_env("PAGE_SUMMARIZER_PROVIDER") or "auto"
    if provider not in _ALLOWED_PROVIDERS:
        allowed = ", ".join(sorted(_ALLOWED_PROVIDERS))
        raise ConfigError(
            f"Недопустимый PAGE_SUMMARIZER_PROVIDER: {provider}. "
            f"Допустимые значения: {allowed}."
        )

    qwen_api_key = _first_env("QWEN_API_KEY", "DOC_ANALYZER_QWEN_API_KEY")
    chutes_api_token = _first_env(
        "CHUTES_API_TOKEN",
        "DOC_ANALYZER_CHUTES_API_TOKEN",
    )

    if provider == "qwen" and not qwen_api_key:
        raise ConfigError(
            "Не задан ключ Qwen. Укажите QWEN_API_KEY или DOC_ANALYZER_QWEN_API_KEY."
        )
    if provider == "chutes" and not chutes_api_token:
        raise ConfigError(
            "Не задан токен Chutes. Укажите CHUTES_API_TOKEN "
            "или DOC_ANALYZER_CHUTES_API_TOKEN."
        )
    if provider == "auto" and not qwen_api_key and not chutes_api_token:
        raise ConfigError(
            "Не задан ни ключ Qwen, ни токен Chutes. "
            "Добавьте их в .env проекта."
        )

    return Settings(
        provider=provider,
        qwen_api_key=qwen_api_key,
        qwen_base_url=_first_env("QWEN_BASE_URL", "DOC_ANALYZER_QWEN_BASE_URL")
        or "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        qwen_model=_first_env("QWEN_MODEL", "DOC_ANALYZER_QWEN_MODEL", "PAGE_SUMMARIZER_MODEL")
        or "qwen-plus",
        chutes_api_token=chutes_api_token,
        chutes_base_url=_first_env("CHUTES_BASE_URL", "DOC_ANALYZER_CHUTES_BASE_URL")
        or "https://llm.chutes.ai/v1",
        chutes_model=_first_env("CHUTES_MODEL", "DOC_ANALYZER_CHUTES_MODEL")
        or "Qwen/Qwen3-32B-TEE",
        request_timeout=_env_float("PAGE_SUMMARIZER_HTTP_TIMEOUT", 20.0),
        llm_timeout=_env_float("PAGE_SUMMARIZER_LLM_TIMEOUT", 90.0),
        max_retries=_env_int("PAGE_SUMMARIZER_MAX_RETRIES", 3),
        max_input_chars=_env_int("PAGE_SUMMARIZER_MAX_INPUT_CHARS", 12_000),
        user_agent=os.getenv(
            "PAGE_SUMMARIZER_USER_AGENT",
            "Mozilla/5.0 (compatible; PageSummarizer/1.0; educational project)",
        ).strip(),
    )
