"""Создание Bot и Dispatcher aiogram, прокси для Telegram (ADR-12, ADR-16)."""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from app.adapters.telegram.handlers import router
from app.config import Settings


def create_bot(settings: Settings) -> Bot:
    """Бот с HTML-разметкой по умолчанию; TELEGRAM_PROXY включает прокси."""
    session = AiohttpSession(proxy=settings.telegram_proxy) if settings.telegram_proxy else None
    return Bot(
        token=settings.bot_token.get_secret_value(),
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    """Диспетчер с подключённым роутером обработчиков."""
    dp = Dispatcher()
    dp.include_router(router)
    return dp
