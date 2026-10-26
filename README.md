# brief-bot

Telegram-бот [@vegorovmsk_brief_bot](https://t.me/vegorovmsk_brief_bot): за 5–7 минут опрашивает
потенциального заказчика о задаче (Telegram-боты, ИИ-агенты, парсинг, интеграции) и собирает
структурированный бриф. Одновременно — демо и кейс для портфолио.

**Статус:** этап 0 (каркас). Бот отвечает на `/start` заглушкой. Полное ТЗ и план этапов —
[docs/TZ.md](docs/TZ.md).

## Стек

Python 3.12 · aiogram 3 · pydantic-settings · structlog · uv · Docker. Дальше по плану: SQLite +
SQLAlchemy, YandexGPT, docxtpl, Google/Яндекс Диск.

## Быстрый старт

```bash
cp .env.example .env        # впишите BOT_TOKEN токен dev-бота
uv sync
uv run python -m app.main   # локально
# или
docker compose up -d --build
```

Для разработки используйте отдельного dev-бота: два процесса с одним токеном конфликтуют.

## Проверки

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest -q
uv run pre-commit install   # ruff, gitleaks и тесты перед каждым коммитом
```

## Структура

- `app/core` — ядро диалога, не зависит от мессенджеров и библиотек
- `app/adapters` — Telegram (и позже VK)
- `app/llm`, `app/storage`, `app/documents`, `app/delivery`, `app/integrations`, `app/jobs`
- `config/` — тексты, банк вопросов, ориентиры цен; `docs/` — ТЗ и разборы этапов
