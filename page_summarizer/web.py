"""Простой веб-интерфейс для агента."""

from __future__ import annotations

import logging
from html import escape

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

from .agent import PageSummarizerAgent
from .exceptions import PageSummarizerError
from .logging_setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Page Summarizer Agent")

_PAGE = """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Агент анализа сайтов</title>
  <style>
    :root { color-scheme: light; }
    body {
      margin: 0;
      font-family: "Segoe UI", "PT Serif", "Times New Roman", serif;
      background: #f4efe6;
      color: #1f1a14;
    }
    main {
      max-width: 760px;
      margin: 48px auto;
      padding: 0 24px 64px;
    }
    h1 {
      font-size: 2rem;
      font-weight: 600;
      margin-bottom: 8px;
    }
    .lead {
      color: #5b5348;
      margin-bottom: 28px;
    }
    form {
      display: flex;
      gap: 12px;
      margin-bottom: 28px;
    }
    input[type="url"] {
      flex: 1;
      padding: 12px 14px;
      border: 1px solid #c9bfb0;
      background: #fffdf8;
      font: inherit;
    }
    button {
      padding: 12px 18px;
      border: 0;
      background: #2c241b;
      color: #f7f1e7;
      font: inherit;
      cursor: pointer;
    }
    .card {
      background: #fffdf8;
      border: 1px solid #ddd2c2;
      padding: 20px 22px;
    }
    .meta {
      margin-top: 16px;
      color: #6a6156;
      font-size: 0.92rem;
    }
    .error { color: #8a2b1e; }
  </style>
</head>
<body>
  <main>
    <h1>Агент анализа сайтов</h1>
    <p class="lead">Вставьте ссылку — агент извлечёт основной текст и сделает резюме из 3–5 предложений.</p>
    <form method="post" action="/">
      <input type="url" name="url" placeholder="https://example.com" value="__URL__" required>
      <button type="submit">Суммаризировать</button>
    </form>
    __BODY__
  </main>
</body>
</html>
"""


def _render(*, url: str = "", body: str = "") -> HTMLResponse:
    html = _PAGE.replace("__URL__", escape(url, quote=True)).replace("__BODY__", body)
    return HTMLResponse(html)


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    logger.info("Открыта главная страница веб-интерфейса")
    return _render()


@app.post("/", response_class=HTMLResponse)
def summarize(url: str = Form(...)) -> HTMLResponse:
    logger.info("Веб-запрос на суммаризацию: %s", url)
    try:
        result = PageSummarizerAgent().summarize_url(url)
    except PageSummarizerError as exc:
        logger.exception("Ошибка суммаризации для %s: %s", url, exc)
        return _render(
            url=url,
            body=f'<div class="card error">Ошибка: {escape(str(exc))}</div>',
        )

    logger.info(
        "Веб-ответ готов: provider=%s model=%s sentences=%s",
        result.provider,
        result.model,
        result.sentences_count,
    )
    return _render(
        url=url,
        body=(
            f'<div class="card"><p>{escape(result.summary)}</p>'
            f'<p class="meta">Провайдер: {escape(result.provider)} · '
            f"модель: {escape(result.model)} · "
            f"предложений: {result.sentences_count} · "
            f"символов источника: {result.source_chars}</p></div>"
        ),
    )
