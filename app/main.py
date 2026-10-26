"""Точка входа: ручная сборка зависимостей и запуск polling (ADR-12)."""

import asyncio
import contextlib

import structlog

from app.adapters.telegram.bot import create_bot, create_dispatcher
from app.config import load_settings
from app.healthcheck import HEARTBEAT_PATH
from app.logging_setup import setup_logging

HEARTBEAT_INTERVAL_SECONDS = 30


async def heartbeat() -> None:
    """Раз в 30 секунд обновлять файл-признак живости для healthcheck."""
    while True:
        HEARTBEAT_PATH.touch()
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)


async def main() -> None:
    """Собрать бота и слушать обновления."""
    settings = load_settings()
    setup_logging(settings.env)
    log = structlog.get_logger()

    bot = create_bot(settings)
    dp = create_dispatcher()
    beat = asyncio.create_task(heartbeat())
    log.info("bot_starting", env=settings.env)
    try:
        await dp.start_polling(bot)
    finally:
        beat.cancel()
        await bot.session.close()
        log.info("bot_stopped")


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
