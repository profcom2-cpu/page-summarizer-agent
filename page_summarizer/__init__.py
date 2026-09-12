"""Пакет агента для суммаризации сайтов."""

from .agent import PageSummarizerAgent, SummaryResult, run_agent

__all__ = [
    "PageSummarizerAgent",
    "SummaryResult",
    "run_agent",
]
