"""Тест заглушки /start (этап 0, FR-1)."""

from unittest.mock import AsyncMock

from app.adapters.telegram.handlers import STUB_TEXT, on_start


async def test_start_replies_with_stub() -> None:
    message = AsyncMock()
    await on_start(message)
    message.answer.assert_awaited_once_with(STUB_TEXT)
    assert STUB_TEXT == "Бот в разработке"
