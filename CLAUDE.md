# brief-bot

Telegram-бот @vegorovmsk_brief_bot: опрашивает заказчика о задаче и собирает бриф.
Полное ТЗ — docs/TZ.md. Требования — FR-…, решения — ADR-….

## Команды
- `uv sync` — зависимости
- `uv run python -m app.main` — локальный запуск (dev-бот, .env)
- `uv run pytest -q` — тесты
- `uv run python tools/eval.py` — eval с реальной LLM (платно, только по просьбе владельца)
- `uv run ruff check . && uv run ruff format . && uv run mypy app`
- `uv run alembic revision --autogenerate -m "..."`, `uv run alembic upgrade head`
- `docker compose up -d --build` — запуск в Docker
- Деплой на VPS — docs/DEPLOY.md (вручную, по SSH; доступа к серверу у Claude нет)

## Архитектура
- app/core — ядро диалога; не импортирует aiogram, httpx, openai, sqlalchemy, google, gspread
  (проверяет tests/test_architecture.py)
- app/adapters/* — мессенджеры; app/llm — LLM; app/storage — БД; app/documents — docx;
  app/delivery — облака и почта; app/integrations — таблица и уведомления; app/jobs — фон

## Правила
- Работаем по этапам docs/TZ.md (раздел 13). Новый этап — только после «принято» от владельца.
- Сначала план в режиме планирования, потом код.
- Простой явный код, аннотации типов, docstring на русском. Новые зависимости — только с согласия.
- Секреты только в .env и secrets/; никогда не выводить, не логировать, не коммитить.
- Тексты для заказчика — в config/texts.yaml, не в коде.
- Цены и сроки разработки никогда не показываются заказчику (ADR-06).
- Не делать реальных вызовов LLM, облаков и почты без просьбы; боевой токен бота не использовать.
- В конце этапа — docs/walkthrough/stage-N.md по формату раздела 13.0.
- При необходимости обновить CLAUDE.md по результатам этапа.

## Окружение разработчика
- Windows 11, PowerShell. Файлы с кириллицей читать и писать как UTF-8 без BOM
  (в PowerShell 5.1 `Get-Content` без `-Encoding utf8` портит кодировку).
- Dev-бот и прод-бот — разные токены; два процесса с одним токеном конфликтуют (ADR-12).
