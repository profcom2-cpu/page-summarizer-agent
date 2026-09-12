# Page Summarizer Agent

Агент на Python: по URL загружает страницу, извлекает основной текст и делает краткое резюме из 3–5 предложений.

Модель: **Qwen** (DashScope, OpenAI-совместимый API). Если Qwen недоступен, агент автоматически переключается на **Chutes**.

## Возможности

- Проверка, что ссылка начинается с `http://` или `https://`
- Загрузка HTML с таймаутом, редиректами и повторными попытками
- Извлечение текста через trafilatura, запасной вариант — BeautifulSoup
- Очистка скриптов, стилей, навигации и футера
- Резюме строго 3–5 предложений
- Понятные ошибки вместо необработанных исключений
- CLI и простой веб-интерфейс
- Логи в консоль и в `page_summarizer.log` (уровень `PAGE_SUMMARIZER_LOG_LEVEL`)

## Установка

```powershell
cd "C:\Users\profc\Desktop\итоговый агент"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Ключи можно положить в `.env` рядом с проектом. Если локального `.env` нет, агент подхватит уже настроенные `DOC_ANALYZER_QWEN_API_KEY` и `CHUTES_API_TOKEN` из проекта JuristStudio.

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
python -m page_summarizer https://example.com
```

Веб-интерфейс:

```powershell
uvicorn page_summarizer.web:app --reload --port 8020
```

Откройте http://127.0.0.1:8020

## Демонстрация

Скриншоты, GIF и текст живого запуска лежат в папке [`demo/`](demo/ДЕМОНСТРАЦИЯ.md).

Репозиторий: https://github.com/profcom2-cpu/page-summarizer-agent

## Тесты

```powershell
pytest -q
```

## Структура

```
page_summarizer/
  __main__.py     CLI
  agent.py        цикл анализа и проверка резюме
  extractor.py    загрузка страницы и извлечение текста
  llm.py          Qwen + Chutes
  config.py       настройки из окружения
  exceptions.py   понятные ошибки
  web.py          веб-интерфейс
```
