"""CLI-точка входа."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .agent import PageSummarizerAgent
from .exceptions import PageSummarizerError
from .logging_setup import setup_logging


def main() -> int:
    """Запускает агента из командной строки."""
    parser = argparse.ArgumentParser(
        description="Разбор судебного акта: PDF/DOCX/TXT, текст или URL публикации."
    )
    parser.add_argument(
        "source",
        nargs="?",
        help="Путь к файлу акта или URL опубликованного акта",
    )
    parser.add_argument(
        "--text",
        help="Текст судебного акта (если не указан файл)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Подробные логи",
    )
    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    url = ""
    file_path = ""
    text = args.text or ""
    source = (args.source or "").strip()
    if source.lower().startswith(("http://", "https://")):
        url = source
    elif source:
        file_path = str(Path(source))

    if not url and not file_path and not text.strip():
        parser.error("Укажите файл акта, --text или URL публикации.")

    try:
        agent = PageSummarizerAgent()
        result = agent.analyze(url=url, text=text, file_path=file_path)
        print(result.format_text())
        print(
            "\n"
            f"# Источник: {result.source}; "
            f"провайдер: {result.provider}; "
            f"модель: {result.model}; "
            f"предложений: {result.sentences_count}; "
            f"символов в источнике: {result.source_chars}",
            file=sys.stderr,
        )
        return 0
    except PageSummarizerError as exc:
        logging.getLogger(__name__).exception("Ошибка агента: %s", exc)
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Выполнение прервано пользователем.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
