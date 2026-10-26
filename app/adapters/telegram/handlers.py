"""Обработчики Telegram. Этап 0: только /start в личном чате (FR-1)."""

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router(name="main")
router.message.filter(F.chat.type == "private")

# На этапе 1 текст переедет в config/texts.yaml (NFR-9).
STUB_TEXT = "Бот в разработке"


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    """Ответить заглушкой на /start."""
    await message.answer(STUB_TEXT)
