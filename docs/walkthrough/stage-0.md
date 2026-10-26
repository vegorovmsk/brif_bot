# Разбор этапа 0: каркас

## 1. Что сделано

- Проект на uv (Python 3.12), структура пакетов по разделу 6.3 ТЗ: у каждого модуля docstring, логики нет.
- Настройки (`app/config.py`) и логирование с маскированием телефонов и email (`app/logging_setup.py`).
- Минимальный Telegram-адаптер: `/start` в личном чате отвечает «Бот в разработке» (FR-1).
- Docker (многоэтапная сборка, не root), Compose с томами и healthcheck.
- Качество: ruff, mypy, pytest, pre-commit (ruff, gitleaks, pytest), GitHub Actions.

## 2. Карта модулей

| Файл | За что отвечает |
|---|---|
| `app/main.py` | Сборка зависимостей вручную и запуск polling; фоновая задача heartbeat |
| `app/config.py` | `Settings` (pydantic-settings): все переменные `.env`, секреты — `SecretStr` |
| `app/logging_setup.py` | structlog: JSON в prod, читаемый вывод в dev, процессор `mask_pii` |
| `app/healthcheck.py` | Проверяет, что файл heartbeat свежий (для Docker HEALTHCHECK) |
| `app/adapters/telegram/bot.py` | `create_bot` (прокси, HTML по умолчанию) и `create_dispatcher` |
| `app/adapters/telegram/handlers.py` | Роутер только для личных чатов, хендлер `/start` |
| `tests/test_architecture.py` | Следит, что `app/core` не импортирует внешние библиотеки |

Остальные модули — пустые заготовки с docstring: в них написано, на каком этапе они оживут.

## 3. Путь одного события: `/start`

1. Telegram отдаёт обновление long polling'у: `Dispatcher.start_polling(bot)` в `main.main()`.
2. Диспетчер передаёт его в `router` (`handlers.py`). Фильтр `F.chat.type == "private"` отсекает группы и каналы.
3. Фильтр `CommandStart()` выбирает `on_start`.
4. `on_start` вызывает `message.answer("Бот в разработке")`; aiogram отправляет `sendMessage`.
5. Параллельно `heartbeat()` раз в 30 с обновляет файл; Docker по нему видит, что цикл событий жив.

## 4. Что изучить

- aiogram 3: `Dispatcher`, `Router`, фильтры (`F`, `CommandStart`), `Bot` и `DefaultBotProperties`.
- pydantic-settings: чтение `.env`, `SecretStr`, `env_ignore_empty`.
- structlog: цепочка процессоров, `ProcessorFormatter` для логов стандартной библиотеки.
- Docker: multi-stage build, `HEALTHCHECK`, тома, `restart: unless-stopped`.
- pre-commit и gitleaks.

## 5. Вопросы для самопроверки

<details><summary>1. Почему dev и прод нельзя запускать с одним токеном?</summary>

Long polling допускает одного получателя обновлений. Второй процесс получит `TelegramConflictError`, и оба будут терять сообщения (ADR-12).
</details>

<details><summary>2. Зачем `SecretStr` для токена?</summary>

`repr()` и логи показывают `**********`, поэтому токен не утечёт случайно; значение достаётся явно через `get_secret_value()`.
</details>

<details><summary>3. Почему healthcheck через файл, а не HTTP?</summary>

У бота нет HTTP-порта (polling). Файл обновляется задачей в том же цикле событий: если цикл завис, файл устареет, и Docker пометит контейнер `unhealthy`.
</details>

<details><summary>4. Зачем маскировать ПДн в логах, если логи только у владельца?</summary>

Минимизация ПДн (ADR-07): логи копируются, попадают в отчёты об ошибках и чаты, и там телефонов и email быть не должно.
</details>

<details><summary>5. Зачем тест `test_architecture.py`, если ядро пока пустое?</summary>

Правило «ядро не зависит от aiogram и БД» легче соблюдать с первого дня; тест не даст случайно сделать ядро платформозависимым, и тогда VK и MAX будут работать без переписывания логики (ADR-02).
</details>

## 6. Что упрощено и почему

- Текст заглушки лежит в коде: загрузчик `texts.yaml` появится на этапе 1 вместе с pyyaml.
- Нет БД и Alembic — они нужны с этапа 1.
- CI проверен только локально: remote ещё не подключён.
