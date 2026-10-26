"""Отправка ответов ядра в Telegram: сообщения, правка на месте, уведомления (FR-7)."""

import html
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from app.adapters.telegram.keyboards import contact_keyboard, inline_keyboard
from app.adapters.telegram.render import render_spans
from app.core.replies import DocumentReply, Reply, TextReply, Toast

log = logging.getLogger(__name__)

Markup = InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | None


def _markup(reply: TextReply) -> Markup:
    if reply.buttons:
        return inline_keyboard(reply.buttons)
    if reply.request_contact:
        return contact_keyboard(reply.contact_label)
    if reply.remove_reply_keyboard:
        return ReplyKeyboardRemove()
    return None


def _pressed_label(callback: CallbackQuery) -> str | None:
    """Надпись нажатой кнопки: ищем её в клавиатуре исходного сообщения."""
    message = callback.message
    if not isinstance(message, Message) or message.reply_markup is None:
        return None
    for row in message.reply_markup.inline_keyboard:
        for button in row:
            if button.callback_data == callback.data:
                return button.text
    return None


async def _close_old_keyboard(callback: CallbackQuery) -> None:
    """FR-7: убрать клавиатуру у исходного сообщения и дописать «✔ выбранный вариант»."""
    message = callback.message
    label = _pressed_label(callback)
    if not isinstance(message, Message) or label is None:
        return
    try:
        await message.edit_text(
            f"{message.html_text}\n\n✔ {html.escape(label, quote=False)}", reply_markup=None
        )
    except TelegramBadRequest:
        log.warning("не удалось обновить исходное сообщение")


async def deliver(
    bot: Bot, chat_id: int, replies: list[Reply], callback: CallbackQuery | None = None
) -> None:
    """Показать пользователю ответы ядра по порядку; на callback отвечаем ровно один раз."""
    toasts = [r for r in replies if isinstance(r, Toast)]
    if callback is not None:
        await callback.answer(toasts[0].text if toasts else None)
        first = next((r for r in replies if not isinstance(r, Toast)), None)
        edits_in_place = isinstance(first, TextReply) and first.edit_in_place
        if not toasts and not edits_in_place:
            await _close_old_keyboard(callback)

    for reply in replies:
        if isinstance(reply, Toast):
            continue
        if isinstance(reply, DocumentReply):
            await bot.send_document(
                chat_id,
                BufferedInputFile(reply.content, filename=reply.filename),
                caption=render_spans(reply.caption) or None,
            )
            continue
        text = render_spans(reply.spans)
        if reply.edit_in_place and callback is not None and isinstance(callback.message, Message):
            try:
                await callback.message.edit_text(text, reply_markup=inline_keyboard(reply.buttons))
            except TelegramBadRequest:
                log.info("сообщение не изменилось")
            continue
        await bot.send_message(chat_id, text, reply_markup=_markup(reply))
