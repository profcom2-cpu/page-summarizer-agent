# Анализ судебных актов

Агент на Python: принимает судебный акт (PDF, DOCX, текст или URL публикации), извлекает текст и делает структурированный разбор — суд, номер дела, стороны, резолютив, нормы и краткое резюме.

Модель: **Qwen** (DashScope, OpenAI-совместимый API). Если Qwen недоступен, агент автоматически переключается на **Chutes**.

Это отдельный сервис разбора актов, не конвейер JuristStudio (`court_doc_cli`).

## Возможности

- Вход: файл PDF/DOCX/TXT, вставленный текст или ссылка на опубликованный акт
- Извлечение текста из DOCX и PDF с текстовым слоем; HTML-публикации — через trafilatura / BeautifulSoup
- JSON-разбор: суд, дело, стороны, резолютив, нормы, резюме 3–5 предложений
- Понятные ошибки вместо необработанных исключений
- CLI и простой веб-интерфейс
- Логи в консоль и в `page_summarizer.log` (уровень `PAGE_SUMMARIZER_LOG_LEVEL`)

## Установка

```powershell
cd "C:\Users\profc\Desktop\Курс нейросети для юристов (материалы)\итоговый агент"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Ключи можно положить в `.env` рядом с проектом. Если локального `.env` нет, агент подхватит уже настроенные `DOC_ANALYZER_QWEN_API_KEY` и `CHUTES_API_TOKEN` из проекта JuristStudio. Не перезаписывайте ключи Qwen в JuristStudio.

Пример `.env`:

```env
QWEN_API_KEY=sk-...
QWEN_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-plus
CHUTES_API_TOKEN=cpk_...
PAGE_SUMMARIZER_PROVIDER=auto
```

`PAGE_SUMMARIZER_PROVIDER`: `auto` (Qwen, затем Chutes), `qwen` или `chutes`.

## Запуск

Командная строка:

```powershell
python -m page_summarizer "C:\путь\к\акту.pdf"
python -m page_summarizer --text "Текст судебного акта..."
python -m page_summarizer https://kad.arbitr.ru/...
```

Веб-интерфейс:

```powershell
uvicorn page_summarizer.web:app --reload --port 8020
```

Откройте http://127.0.0.1:8020 — загрузите файл, вставьте текст или укажите ссылку.

## Демонстрация

Скриншоты прежнего веб-интерфейса (ещё как анализатор сайтов) лежат в [`demo/`](demo/ДЕМОНСТРАЦИЯ.md). Поля формы обновлены под судебные акты.

Репозиторий: https://github.com/profcom2-cpu/page-summarizer-agent

## Тесты

```powershell
pytest -q
```

## Структура

```
page_summarizer/
  __main__.py     CLI
  agent.py        цикл разбора акта и проверка JSON
  extractor.py    PDF/DOCX/TXT и загрузка публикации
  llm.py          Qwen + Chutes
  config.py       настройки из окружения
  exceptions.py   понятные ошибки
  web.py          веб-интерфейс
```
