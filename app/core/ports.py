"""Интерфейсы, от которых зависит ядро; реализации подставляются в app/main.py (ТЗ, 6.2)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from pydantic import BaseModel

from app.core.events import UserRef
from app.core.models import Analysis, Brief, BriefDraft, BriefRevision
from app.core.replies import Span
from app.core.session import Session, SessionData


class User(BaseModel):
    """Пользователь, давший согласие."""

    id: int
    platform: str
    platform_user_id: str
    username: str | None = None
    first_name: str | None = None
    consent_at: datetime
    consent_version: str


class Contact(BaseModel):
    """Контакт заказчика: все ПДн — здесь (ADR-07)."""

    name: str
    phone: str | None = None
    email: str | None = None
    username: str | None = None
    preferred_method: str


@dataclass(frozen=True)
class FinalizeInfo:
    """Всё, что нужно владельцу для уведомления о подтверждённом брифе."""

    brief: Brief
    contact: Contact
    source: str | None
    platform: str


class Clock(Protocol):
    """Текущее время (по Москве); в тестах подменяется."""

    def now(self) -> datetime: ...


class UserRepository(Protocol):
    """Пользователи."""

    async def get(self, platform: str, platform_user_id: str) -> User | None: ...

    async def upsert_consented(self, ref: UserRef, consent_version: str, now: datetime) -> User: ...

    async def delete_all_data(self, user_id: int) -> None:
        """Удалить пользователя со всем, что с ним связано (FR-44)."""
        ...


class SessionRepository(Protocol):
    """Сессии диалога."""

    async def get_active(self, user_id: int) -> Session | None: ...

    async def create(self, session: Session, now: datetime) -> Session: ...

    async def save(self, session: Session, now: datetime) -> None: ...

    async def delete(self, session_id: int) -> None: ...


class BriefRepository(Protocol):
    """Подтверждённые брифы."""

    async def create_confirmed(
        self,
        *,
        day: date,
        build: Callable[[str], Brief],
        session_id: int,
        user_id: int,
        now: datetime,
    ) -> Brief:
        """Выдать ID вида B-ГГММДД-NNN, собрать бриф через build(id) и сохранить (FR-23)."""
        ...

    async def count_confirmed_since(self, user_id: int, since: datetime) -> int: ...

    async def get_finalize_info(self, brief_id: str) -> FinalizeInfo | None: ...


class ContactRepository(Protocol):
    """Контакты заказчиков."""

    async def save(self, user_id: int, contact: Contact, now: datetime) -> None: ...


class AuditLog(Protocol):
    """Журнал событий без ПДн: пользователь хранится только как хеш."""

    async def record(self, event: str, ref: UserRef, now: datetime) -> None: ...


class Outbox(Protocol):
    """Фоновые задачи после подтверждения брифа (на этапе 1 — InlineFinalizer)."""

    async def enqueue_finalize(self, brief_id: str) -> None: ...


class BriefAI(Protocol):
    """Вызовы LLM, тексты которых видит заказчик (ADR-06).

    None во всех методах значит «LLM недоступна»: она выключена, исчерпан бюджет, случилась
    ошибка или ответ нарушил проверки после повтора. Запасной путь выбирает ядро (ТЗ, 11.8).
    """

    async def analyze(self, description: str, *, session_id: int) -> Analysis | None: ...

    async def synthesize(self, data: SessionData, *, session_id: int) -> BriefDraft | None: ...

    async def revise(
        self, draft: BriefDraft, correction: str, *, session_id: int
    ) -> BriefRevision | None: ...


class LLMSwitch(Protocol):
    """Переключатель LLM владельцем: /llm on|off (ТЗ, 3.3). Значение переживает перезапуск."""

    async def is_enabled(self) -> bool: ...

    async def set_enabled(self, enabled: bool) -> None: ...


class ReviewRenderer(Protocol):
    """Сокращённый бриф для проверки в чате: разделы из фрагментов текста (раздел 10.9)."""

    def render(self, brief: Brief) -> list[list[Span]]: ...
