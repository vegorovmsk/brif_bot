"""Уведомления владельцу в Telegram (реализация OwnerNotifier)."""

import structlog
from aiogram import Bot

log = structlog.get_logger()


class TelegramOwnerNotifier:
    """Шлёт HTML-сообщения в OWNER_CHAT_ID; без него — только запись в лог."""

    def __init__(self, bot: Bot, chat_id: int | None) -> None:
        self._bot = bot
        self._chat_id = chat_id

    async def send_html(self, text: str) -> None:
        if self._chat_id is None:
            log.warning("owner_chat_id_not_set")
            return
        await self._bot.send_message(self._chat_id, text)
