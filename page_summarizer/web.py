"""Простой веб-интерфейс для разбора судебных актов."""

from __future__ import annotations

import logging
from html import escape

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse

from .agent import PageSummarizerAgent
from .exceptions import PageSummarizerError
from .logging_setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Анализ судебных актов")

_PAGE = """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Анализ судебных актов</title>
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
      flex-direction: column;
      gap: 12px;
      margin-bottom: 28px;
    }
    input[type="url"],
    input[type="file"],
    textarea {
      width: 100%;
      box-sizing: border-box;
      padding: 12px 14px;
      border: 1px solid #c9bfb0;
      background: #fffdf8;
      font: inherit;
    }
    textarea { min-height: 160px; resize: vertical; }
    button {
      align-self: flex-start;
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
    dt {
      font-weight: 600;
      margin-top: 12px;
    }
    dt:first-child { margin-top: 0; }
    dd {
      margin: 4px 0 0;
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
    <h1>Анализ судебных актов</h1>
    <p class="lead">Загрузите PDF/DOCX, вставьте текст акта или укажите ссылку на публикацию — агент извлечёт суд, дело, стороны, резолютив и нормы.</p>
    <form method="post" action="/" enctype="multipart/form-data">
      <input type="file" name="document" accept=".pdf,.docx,.txt,.md,application/pdf">
      <textarea name="text" placeholder="Или вставьте текст судебного акта">__TEXT__</textarea>
      <input type="url" name="url" placeholder="Или ссылка на опубликованный акт" value="__URL__">
      <button type="submit">Разобрать акт</button>
    </form>
    __BODY__
  </main>
</body>
</html>
"""


def _render(*, url: str = "", text: str = "", body: str = "") -> HTMLResponse:
    html = (
        _PAGE.replace("__URL__", escape(url, quote=True))
        .replace("__TEXT__", escape(text))
        .replace("__BODY__", body)
    )
    return HTMLResponse(html)


def _result_card(result) -> str:
    rows = (
        ("Суд", result.court),
        ("Дело", result.case_number),
        ("Стороны", result.parties),
        ("Резолютив", result.operative_part),
        ("Нормы", result.norms),
        ("Резюме", result.summary),
    )
    items = "".join(
        f"<dt>{escape(label)}</dt><dd>{escape(value)}</dd>" for label, value in rows
    )
    return (
        f'<div class="card"><dl>{items}</dl>'
        f'<p class="meta">Источник: {escape(result.source)} · '
        f"провайдер: {escape(result.provider)} · "
        f"модель: {escape(result.model)} · "
        f"предложений в резюме: {result.sentences_count} · "
        f"символов источника: {result.source_chars}</p></div>"
    )


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    logger.info("Открыта главная страница веб-интерфейса")
    return _render()


@app.post("/", response_class=HTMLResponse)
async def analyze(
    url: str = Form(""),
    text: str = Form(""),
    document: UploadFile | None = File(None),
) -> HTMLResponse:
    filename = (document.filename or "").strip() if document is not None else ""
    file_bytes = await document.read() if document is not None and filename else None
    if file_bytes == b"":
        file_bytes = None

    logger.info(
        "Веб-запрос на разбор акта: file=%s url=%s text_chars=%s",
        filename or "-",
        url or "-",
        len(text or ""),
    )
    try:
        result = PageSummarizerAgent().analyze(
            url=url,
            text=text,
            file_bytes=file_bytes,
            filename=filename,
        )
    except PageSummarizerError as exc:
        logger.exception("Ошибка разбора акта: %s", exc)
        return _render(
            url=url,
            text=text,
            body=f'<div class="card error">Ошибка: {escape(str(exc))}</div>',
        )

    logger.info(
        "Веб-ответ готов: provider=%s model=%s sentences=%s",
        result.provider,
        result.model,
        result.sentences_count,
    )
    return _render(url=url, text=text, body=_result_card(result))
