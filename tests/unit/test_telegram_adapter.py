"""Тесты адаптера Telegram: рендер, клавиатуры, троттлинг, блокировка, старт-команды."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from aiogram.types import CallbackQuery, Chat, Message, User

from app.adapters.telegram.keyboards import contact_keyboard, inline_keyboard
from app.adapters.telegram.middlewares import PrivateChatOnly, Throttle, UserLock
from app.adapters.telegram.render import render_spans
from app.core.replies import Button, Span


def test_render_escapes_customer_text() -> None:
    html = render_spans([Span("<script>alert(1)</script> & co", bold=True)])
    assert html == "<b>&lt;script&gt;alert(1)&lt;/script&gt; &amp; co</b>"


def test_render_link_and_italic() -> None:
    html = render_spans([Span("сайт", italic=True, link='https://a.b/?x="1"&y=2')])
    assert html == '<a href="https://a.b/?x=&quot;1&quot;&amp;y=2"><i>сайт</i></a>'


def test_keyboards() -> None:
    markup = inline_keyboard([[Button("Да", "3:cy")], [Button("Нет", "3:cn")]])
    assert markup.inline_keyboard[0][0].callback_data == "3:cy"
    keyboard = contact_keyboard("Поделиться")
    assert keyboard.keyboard[0][0].request_contact is True


def test_fr8_throttle_drops_events_over_limit() -> None:
    throttle = Throttle(limit=3, window_seconds=60)
    assert [throttle.allow(1, now=t) for t in (0, 1, 2, 3)] == [True, True, True, False]
    assert throttle.allow(2, now=3)  # другой пользователь не затронут
    assert throttle.allow(1, now=61)  # окно сдвинулось


def _message(chat_type: str = "private", user_id: int = 7) -> Message:
    return Message(
        message_id=1,
        date=datetime.now(UTC),
        chat=Chat(id=user_id, type=chat_type),
        from_user=User(id=user_id, is_bot=False, first_name="Иван"),
    )


def _callback(user_id: int = 7) -> CallbackQuery:
    return CallbackQuery(
        id="1",
        from_user=User(id=user_id, is_bot=False, first_name="Иван"),
        chat_instance="x",
        message=_message(user_id=user_id),
        data="1:cy",
    )


async def test_fr1_private_chat_only() -> None:
    handler = AsyncMock(return_value="ok")
    guard = PrivateChatOnly()
    assert await guard(handler, _message("supergroup"), {}) is None
    assert await guard(handler, _message("private"), {}) == "ok"
    handler.assert_awaited_once()


async def test_fr6_busy_user_gets_wait_message_instead_of_queue() -> None:
    release = asyncio.Event()

    async def slow_handler(event: object, data: dict[str, object]) -> str:
        await release.wait()
        return "done"

    guard = UserLock("⏳ Секунду")
    with patch.object(CallbackQuery, "answer", new=AsyncMock()) as answer:
        running = asyncio.create_task(guard(slow_handler, _callback(), {}))
        await asyncio.sleep(0)
        assert await guard(slow_handler, _callback(), {}) is None
        answer.assert_awaited_once_with("⏳ Секунду")
        release.set()
        assert await running == "done"
