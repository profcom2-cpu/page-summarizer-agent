"""Настройка логирования в консоль и файл. Ключи API не пишутся."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from .config import load_environment

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_LOG_FILE = _PROJECT_ROOT / "page_summarizer.log"
_CONFIGURED = False


def setup_logging(*, verbose: bool = False) -> Path:
    """Включает логирование агента в консоль и в page_summarizer.log."""
    global _CONFIGURED

    load_environment()
    raw_level = os.getenv("PAGE_SUMMARIZER_LOG_LEVEL", "").strip().upper()
    if verbose or raw_level == "DEBUG":
        level = logging.DEBUG
    elif raw_level:
        level = getattr(logging, raw_level, logging.INFO)
    else:
        level = logging.INFO

    raw_path = os.getenv("PAGE_SUMMARIZER_LOG_FILE", str(_DEFAULT_LOG_FILE))
    log_path = Path(raw_path)
    if not log_path.is_absolute():
        log_path = _PROJECT_ROOT / log_path

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    if _CONFIGURED:
        root.setLevel(level)
        return log_path

    root.setLevel(level)

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    logging.getLogger("httpx").setLevel(logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.INFO)
    logging.getLogger("httpcore2").setLevel(logging.INFO)
    logging.getLogger("openai").setLevel(logging.INFO)
    logging.getLogger("httpx2").setLevel(logging.INFO)
    logging.getLogger("trafilatura").setLevel(logging.INFO)

    _CONFIGURED = True
    logging.getLogger(__name__).info(
        "Логирование включено. Уровень=%s, файл=%s",
        logging.getLevelName(level),
        log_path,
    )
    return log_path
