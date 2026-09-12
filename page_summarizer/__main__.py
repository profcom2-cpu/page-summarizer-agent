"""CLI-точка входа."""

from __future__ import annotations

import argparse
import logging
import sys

from .agent import PageSummarizerAgent
from .exceptions import PageSummarizerError
from .logging_setup import setup_logging


def main() -> int:
    """Запускает агента из командной строки."""
    parser = argparse.ArgumentParser(
        description="Агент для краткого резюме сайта по URL."
    )
    parser.add_argument("url", help="Адрес сайта, например https://example.com")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Подробные логи",
    )
    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    try:
        agent = PageSummarizerAgent()
        result = agent.summarize_url(args.url)
        print(result.summary)
        print(
            "\n"
            f"# Провайдер: {result.provider}; "
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
