# Анализ судебных актов

Агент на Python: принимает судебный акт (PDF, DOCX, текст или URL публикации), извлекает текст и делает структурированный разбор — суд, номер дела, стороны, резолютив, нормы и краткое резюме.

Модель: **Qwen Token Plan** (`qwen3.8-max` / чат-боты `qwen3.8-flash`). Chutes не вызывается, пока квота пустая (`PAGE_SUMMARIZER_CHUTES_ENABLED=false`; ключ можно оставить в `.env`).

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

Ключи можно положить в `.env` рядом с проектом. Локальный `.env` имеет приоритет: если в нём старый workspace-ключ Qwen, подписка Token Plan из JuristStudio **не** подхватится. Если локального `.env` нет, агент берёт `DOC_ANALYZER_QWEN_API_KEY` и `CHUTES_API_TOKEN` из JuristStudio.

Пример `.env`:

```env
QWEN_API_KEY=sk-sp-...
QWEN_BASE_URL=https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen3.8-max
CHUTES_API_TOKEN=cpk_...
CHUTES_MODEL=zai-org/GLM-5.1-TEE
PAGE_SUMMARIZER_PROVIDER=qwen
PAGE_SUMMARIZER_CHUTES_ENABLED=false
```

`PAGE_SUMMARIZER_PROVIDER`: `qwen` (по умолчанию), `auto` (Qwen, затем Chutes **только** если `PAGE_SUMMARIZER_CHUTES_ENABLED=true`) или `chutes`.

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
