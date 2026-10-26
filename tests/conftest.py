"""Общие фикстуры: реальные тексты и банк, SQLite во временной папке, фейковые часы и outbox."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.context import Context, EngineConfig
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
from app.core.question_bank import QuestionBank, load_question_bank
from app.core.replies import Button, Reply, TextReply, Toast
from app.core.texts import Texts, load_texts
from app.documents.review import TextReviewRenderer
from app.storage.db import create_engine, create_session_factory
from app.storage.repositories import (
    SessionFactory,
    SqlAuditLog,
    SqlBriefRepository,
    SqlContactRepository,
    SqlSessionRepository,
    SqlUserRepository,
)
from app.storage.tables import Base

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
MSK = timezone(timedelta(hours=3), "MSK")


class FakeClock:
    """Часы, которыми управляет тест."""

    def __init__(self) -> None:
        self.current = datetime(2026, 10, 26, 12, 0, tzinfo=MSK)

    def now(self) -> datetime:
        return self.current


@dataclass
class FakeOutbox:
    """Запоминает ID брифов, по которым ушла бы фоновая задача."""

    brief_ids: list[str] = field(default_factory=list)

    async def enqueue_finalize(self, brief_id: str) -> None:
        self.brief_ids.append(brief_id)


@dataclass
class World:
    """Всё окружение сценария: БД, часы, outbox и фабрика движков."""

    db: AsyncEngine
    factory: SessionFactory
    clock: FakeClock
    outbox: FakeOutbox
    texts: Texts
    bank: QuestionBank

    def make_engine(self, **config: object) -> ConversationEngine:
        """Новый движок на той же БД — так выглядит перезапуск бота."""
        settings: dict[str, object] = {"owner_username": "vegorovmsk", "consent_version": "v1"}
        settings.update(config)
        ctx = Context(
            users=SqlUserRepository(self.factory),
            sessions=SqlSessionRepository(self.factory),
            briefs=SqlBriefRepository(self.factory),
            contacts=SqlContactRepository(self.factory),
            audit=SqlAuditLog(self.factory, salt="test"),
            outbox=self.outbox,
            review=TextReviewRenderer(),
            clock=self.clock,
            texts=self.texts,
            bank=self.bank,
            config=EngineConfig(**settings),  # type: ignore[arg-type]
        )
        return ConversationEngine(ctx)


@pytest.fixture
async def world(tmp_path: Path) -> AsyncIterator[World]:
    db = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield World(
        db=db,
        factory=create_session_factory(db),
        clock=FakeClock(),
        outbox=FakeOutbox(),
        texts=load_texts(CONFIG_DIR / "texts.yaml"),
        bank=load_question_bank(CONFIG_DIR / "question_bank.yaml"),
    )
    await db.dispose()


def make_user(user_id: int = 1001, username: str | None = "ivan_petrov") -> UserRef:
    """Заказчик из Telegram."""
    return UserRef("telegram", str(user_id), username, "Иван")


class Chat:
    """Переписка одного заказчика с движком: отправляем события, смотрим ответы."""

    def __init__(self, engine: ConversationEngine, user: UserRef) -> None:
        self.engine = engine
        self.user = user
        self.last: list[Reply] = []
        self._visible: list[Button] = []  # кнопки последнего сообщения, где они были
        self.bot_messages = 0

    async def send(self, event: Event) -> list[Reply]:
        self.last = await self.engine.handle(self.user, event)
        self.bot_messages += sum(isinstance(r, TextReply) for r in self.last)
        shown = self._buttons_of(self.last)
        if shown:
            self._visible = shown
        return self.last

    async def text(self, text: str) -> list[Reply]:
        return await self.send(TextInput(text))

    async def cmd(self, name: str, args: str = "") -> list[Reply]:
        return await self.send(CommandInput(name, args))

    async def contact(self, phone: str, own: bool = True) -> list[Reply]:
        return await self.send(ContactShared(phone, own))

    async def unsupported(self, kind: str = "voice") -> list[Reply]:
        return await self.send(UnsupportedInput(kind))

    async def payload(self, payload: str) -> list[Reply]:
        return await self.send(ButtonPress(payload))

    @staticmethod
    def _buttons_of(replies: list[Reply]) -> list[Button]:
        return [b for r in replies if isinstance(r, TextReply) for row in r.buttons for b in row]

    def buttons(self) -> list[Button]:
        return self._visible

    async def press(self, label: str) -> list[Reply]:
        """Нажать кнопку из последних ответов по подписи (точно, затем по вхождению)."""
        buttons = self.buttons()
        found = next((b for b in buttons if b.label == label), None) or next(
            (b for b in buttons if label in b.label), None
        )
        assert found is not None, f"нет кнопки {label!r}; есть: {[b.label for b in buttons]}"
        return await self.payload(found.payload)

    def said(self) -> str:
        """Весь текст последних ответов (без форматирования)."""
        parts = []
        for reply in self.last:
            if isinstance(reply, TextReply):
                parts.append("".join(span.text for span in reply.spans))
            elif isinstance(reply, Toast):
                parts.append(reply.text)
        return "\n".join(parts)


DESCRIPTION = "Нужен бот, который отвечает клиентам по прайсу и собирает заявки"


async def pass_to_contact_method(chat: Chat) -> None:
    """Пройти сценарий от /start до выбора способа связи (путь «ИИ-ассистент»)."""
    await chat.cmd("start")
    if any(b.label == "Согласен, начнём" for b in chat.buttons()):
        await chat.press("Согласен")
    await chat.text(DESCRIPTION)
    await chat.press("ИИ-ассистент")
    for _ in range(4):
        await chat.press("Пропустить")
    await chat.press("2–4 недели")
    await chat.press("10–30 тыс.")
    await chat.press("ТЗ или описание")
    await chat.press("Готово")
    await chat.press("Иван")


async def complete_brief(chat: Chat) -> None:
    """Полный бриф до DONE: связь через Telegram, подтверждение «Всё верно»."""
    await pass_to_contact_method(chat)
    await chat.press("Telegram (@")
    await chat.press("Всё верно")
