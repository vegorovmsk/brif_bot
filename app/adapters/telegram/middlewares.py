"""Middleware: только личные чаты (FR-1), троттлинг (FR-8), блокировка на пользователя (FR-6)."""

import asyncio
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]


def _chat_type(event: TelegramObject) -> str | None:
    if isinstance(event, Message):
        return event.chat.type
    if isinstance(event, CallbackQuery) and event.message is not None:
        return event.message.chat.type
    return None


def _user_id(event: TelegramObject) -> int | None:
    user = getattr(event, "from_user", None)
    return user.id if user else None


class PrivateChatOnly(BaseMiddleware):
    """Игнорирует всё, что пришло не из личного чата."""

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        if _chat_type(event) != "private":
            return None
        return await handler(event, data)


class Throttle(BaseMiddleware):
    """Не больше limit событий в минуту от пользователя; лишние молча отбрасываются."""

    def __init__(self, limit: int, window_seconds: float = 60.0) -> None:
        self._limit = limit
        self._window = window_seconds
        self._hits: dict[int, deque[float]] = defaultdict(deque)

    def allow(self, user_id: int, now: float | None = None) -> bool:
        """Учесть событие и сказать, можно ли его обработать."""
        moment = time.monotonic() if now is None else now
        hits = self._hits[user_id]
        while hits and moment - hits[0] >= self._window:
            hits.popleft()
        if len(hits) >= self._limit:
            return False
        hits.append(moment)
        return True

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        user_id = _user_id(event)
        if user_id is not None and not self.allow(user_id):
            return None
        return await handler(event, data)


class UserLock(BaseMiddleware):
    """События одного пользователя идут строго по одному; занято — ответ «Секунду…» (FR-6)."""

    def __init__(self, busy_text: str) -> None:
        self._busy_text = busy_text
        self._locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        user_id = _user_id(event)
        if user_id is None:
            return await handler(event, data)
        lock = self._locks[user_id]
        if lock.locked():
            if isinstance(event, CallbackQuery):
                await event.answer(self._busy_text)
            elif isinstance(event, Message):
                await event.answer(self._busy_text)
            return None
        async with lock:
            return await handler(event, data)
