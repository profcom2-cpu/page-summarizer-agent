"""Кастомные исключения проекта."""


class PageSummarizerError(Exception):
    """Базовая ошибка агента."""


class ConfigError(PageSummarizerError):
    """Ошибка конфигурации или переменных окружения."""


class FetchError(PageSummarizerError):
    """Ошибка загрузки страницы."""


class ExtractionError(PageSummarizerError):
    """Ошибка извлечения полезного текста."""


class LLMError(PageSummarizerError):
    """Ошибка работы с LLM."""


class ValidationError(PageSummarizerError):
    """Ошибка проверки результата."""
