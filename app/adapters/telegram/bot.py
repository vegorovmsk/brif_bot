"""Создание Bot и Dispatcher aiogram, меню команд, прокси для Telegram (ADR-12, ADR-16)."""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from app.adapters.telegram.handlers import USER_COMMANDS, router
from app.adapters.telegram.middlewares import PrivateChatOnly, Throttle, UserLock
from app.config import Settings
from app.core.engine import ConversationEngine
from app.core.texts import Texts


def create_bot(settings: Settings) -> Bot:
    """Бот с HTML-разметкой по умолчанию; TELEGRAM_PROXY включает прокси."""
    session = AiohttpSession(proxy=settings.telegram_proxy) if settings.telegram_proxy else None
    return Bot(
        token=settings.bot_token.get_secret_value(),
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(engine: ConversationEngine, settings: Settings, texts: Texts) -> Dispatcher:
    """Диспетчер: движок через workflow data, middleware — одни и те же для сообщений и кнопок."""
    dp = Dispatcher(engine=engine)
    guards = [PrivateChatOnly(), Throttle(settings.rate_limit_per_minute), UserLock(texts.busy)]
    for guard in guards:
        dp.message.outer_middleware(guard)
        dp.callback_query.outer_middleware(guard)
    dp.include_router(router)
    return dp


async def setup_commands(bot: Bot, texts: Texts) -> None:
    """Меню команд для всех пользователей (владельческие команды — этап 5)."""
    commands = [
        BotCommand(command=name, description=texts.commands[name]) for name in USER_COMMANDS
    ]
    await bot.set_my_commands(commands)
