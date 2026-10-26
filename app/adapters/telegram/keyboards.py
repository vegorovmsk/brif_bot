"""Button -> клавиатуры Telegram."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.core.replies import Button


def inline_keyboard(rows: list[list[Button]]) -> InlineKeyboardMarkup:
    """Inline-клавиатура: payload кнопки становится callback_data."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=b.label, callback_data=b.payload) for b in row]
            for row in rows
        ]
    )


def contact_keyboard(label: str) -> ReplyKeyboardMarkup:
    """Reply-клавиатура с кнопкой «Поделиться контактом» (работает только в личном чате)."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=label, request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
