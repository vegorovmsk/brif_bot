"""Точка входа: ручная сборка зависимостей и запуск polling (ADR-12)."""

import asyncio
import contextlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog
import yaml
from alembic import command
from alembic.config import Config
from pydantic import ValidationError

from app.adapters.telegram.bot import create_bot, create_dispatcher, setup_commands
from app.adapters.telegram.notifier import TelegramOwnerNotifier
from app.config import Settings, load_settings
from app.core.context import Context, EngineConfig
from app.core.engine import ConversationEngine
from app.core.question_bank import QuestionBank, load_question_bank
from app.core.texts import Texts, load_texts
from app.documents.review import TextReviewRenderer
from app.healthcheck import HEARTBEAT_PATH
from app.integrations.owner import InlineFinalizer
from app.logging_setup import setup_logging
from app.storage.db import create_engine, create_session_factory
from app.storage.repositories import (
    SqlAuditLog,
    SqlBriefRepository,
    SqlContactRepository,
    SqlSessionRepository,
    SqlUserRepository,
)

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
HEARTBEAT_INTERVAL_SECONDS = 30
MSK = timezone(timedelta(hours=3), "MSK")  # в Москве нет перехода на летнее время


class SystemClock:
    """Часы по московскому времени; реализует порт Clock."""

    def now(self) -> datetime:
        return datetime.now(MSK)


def load_content() -> tuple[Texts, QuestionBank]:
    """Тексты и банк вопросов; ошибка в файлах — понятное сообщение вместо запуска (ADR-14)."""
    try:
        return load_texts(CONFIG_DIR / "texts.yaml"), load_question_bank(
            CONFIG_DIR / "question_bank.yaml"
        )
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        sys.exit(f"Ошибка в файлах config/: {exc}")


def run_migrations(database_url: str) -> None:
    """Привести БД к последней версии схемы (Alembic) до запуска цикла событий."""
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")


async def heartbeat() -> None:
    """Раз в 30 секунд обновлять файл-признак живости для healthcheck."""
    while True:
        HEARTBEAT_PATH.touch()
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)


async def main(settings: Settings) -> None:
    """Собрать зависимости вручную и слушать обновления."""
    log = structlog.get_logger()
    texts, bank = load_content()

    db_engine = create_engine(settings.database_url)
    factory = create_session_factory(db_engine)
    briefs = SqlBriefRepository(factory)
    salt = settings.audit_hash_salt.get_secret_value() if settings.audit_hash_salt else ""

    bot = create_bot(settings)
    notifier = TelegramOwnerNotifier(bot, settings.owner_chat_id or settings.owner_telegram_id)
    ctx = Context(
        users=SqlUserRepository(factory),
        sessions=SqlSessionRepository(factory),
        briefs=briefs,
        contacts=SqlContactRepository(factory),
        audit=SqlAuditLog(factory, salt),
        outbox=InlineFinalizer(briefs, notifier),
        review=TextReviewRenderer(),
        clock=SystemClock(),
        texts=texts,
        bank=bank,
        config=EngineConfig(
            owner_username=settings.owner_username,
            consent_version=settings.consent_version,
            privacy_policy_url=settings.privacy_policy_url,
            max_briefs_per_user_per_day=settings.max_briefs_per_user_per_day,
            max_revisions=settings.max_revisions,
        ),
    )
    dp = create_dispatcher(ConversationEngine(ctx), settings, texts)

    beat = asyncio.create_task(heartbeat())
    log.info("bot_starting", env=settings.env)
    try:
        await setup_commands(bot, texts)
        await dp.start_polling(bot)
    finally:
        beat.cancel()
        await bot.session.close()
        await db_engine.dispose()
        log.info("bot_stopped")


def run() -> None:
    """Прочитать настройки, обновить схему БД и запустить бота."""
    settings = load_settings()
    setup_logging(settings.env)
    run_migrations(settings.database_url)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main(settings))


if __name__ == "__main__":
    run()
