"""Обработчики Telegram: превращают обновления в события ядра и показывают ответы (ТЗ, 6.7)."""

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from aiogram.types import User as TgUser

from app.adapters.telegram.sender import deliver
from app.core.engine import ConversationEngine
from app.core.events import (
    ButtonPress,
    CommandInput,
    ContactShared,
    Event,
    TextInput,
    UnsupportedInput,
    UserRef,
)

router = Router(name="main")

USER_COMMANDS = ("start", "new", "cancel", "help", "privacy", "delete_my_data")


def user_ref(user: TgUser) -> UserRef:
    """Пользователь Telegram -> UserRef ядра."""
    return UserRef(
        platform="telegram",
        platform_user_id=str(user.id),
        username=user.username,
        first_name=user.first_name,
    )


async def _process(
    bot: Bot,
    engine: ConversationEngine,
    tg_user: TgUser,
    chat_id: int,
    event: Event,
    callback: CallbackQuery | None = None,
) -> None:
    replies = await engine.handle(user_ref(tg_user), event)
    await deliver(bot, chat_id, replies, callback)


@router.message(Command(*USER_COMMANDS))
async def on_command(
    message: Message, command: CommandObject, bot: Bot, engine: ConversationEngine
) -> None:
    """Известные команды; параметр /start — источник (deep link, FR-12)."""
    if message.from_user is None:
        return
    event = CommandInput(name=command.command.lower(), args=command.args or "")
    await _process(bot, engine, message.from_user, message.chat.id, event)


@router.message(F.text.startswith("/"))
async def on_unknown_command(message: Message, bot: Bot, engine: ConversationEngine) -> None:
    """Неизвестная команда (в том числе владельческая от чужого — FR-37)."""
    if message.from_user is None or not message.text:
        return
    name = message.text.split()[0][1:].split("@")[0].lower()
    await _process(bot, engine, message.from_user, message.chat.id, CommandInput(name=name))


@router.message(F.contact)
async def on_contact(message: Message, bot: Bot, engine: ConversationEngine) -> None:
    """Контакт из кнопки; «свой» ли он — решает сравнение user_id (FR-27)."""
    if message.from_user is None or message.contact is None:
        return
    contact = message.contact
    event = ContactShared(
        phone=contact.phone_number, is_own=contact.user_id == message.from_user.id
    )
    await _process(bot, engine, message.from_user, message.chat.id, event)


@router.message(F.text)
async def on_text(message: Message, bot: Bot, engine: ConversationEngine) -> None:
    """Обычный текст."""
    if message.from_user is None or message.text is None:
        return
    await _process(bot, engine, message.from_user, message.chat.id, TextInput(message.text))


@router.message()
async def on_unsupported(message: Message, bot: Bot, engine: ConversationEngine) -> None:
    """Голос, фото, файлы, стикеры и прочее."""
    if message.from_user is None:
        return
    event = UnsupportedInput(kind=str(message.content_type))
    await _process(bot, engine, message.from_user, message.chat.id, event)


@router.callback_query()
async def on_callback(callback: CallbackQuery, bot: Bot, engine: ConversationEngine) -> None:
    """Нажатие inline-кнопки."""
    if callback.data is None or callback.message is None:
        await callback.answer()
        return
    await _process(
        bot,
        engine,
        callback.from_user,
        callback.message.chat.id,
        ButtonPress(callback.data),
        callback,
    )
