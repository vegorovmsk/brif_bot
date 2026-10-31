"""Реализации портов ядра поверх SQLAlchemy (ТЗ, 6.2, ADR-03)."""

import hashlib
from collections.abc import Callable
from datetime import UTC, date, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.events import UserRef
from app.core.models import Brief
from app.core.ports import Contact, FinalizeInfo, User
from app.core.session import Session, SessionData, SessionStatus
from app.core.states import State
from app.llm.costs import LLMCall
from app.storage.tables import (
    AuditLogRow,
    BotSettingRow,
    BriefRow,
    ContactRow,
    LLMCallRow,
    SessionRow,
    UserRow,
)

SessionFactory = async_sessionmaker[AsyncSession]
_ID_ATTEMPTS = 5


def to_db(moment: datetime) -> datetime:
    """Время с поясом -> UTC без пояса (так оно лежит в SQLite)."""
    return moment.astimezone(UTC).replace(tzinfo=None)


def from_db(moment: datetime) -> datetime:
    """UTC без пояса из SQLite -> время с поясом UTC."""
    return moment.replace(tzinfo=UTC)


def _user(row: UserRow) -> User:
    return User(
        id=row.id,
        platform=row.platform,
        platform_user_id=row.platform_user_id,
        username=row.username,
        first_name=row.first_name,
        consent_at=from_db(row.consent_at),
        consent_version=row.consent_version,
    )


class SqlUserRepository:
    """Пользователи."""

    def __init__(self, factory: SessionFactory) -> None:
        self._factory = factory

    async def get(self, platform: str, platform_user_id: str) -> User | None:
        async with self._factory() as db:
            row = await db.scalar(
                select(UserRow).where(
                    UserRow.platform == platform, UserRow.platform_user_id == platform_user_id
                )
            )
            return _user(row) if row else None

    async def upsert_consented(self, ref: UserRef, consent_version: str, now: datetime) -> User:
        async with self._factory() as db:
            row = await db.scalar(
                select(UserRow).where(
                    UserRow.platform == ref.platform,
                    UserRow.platform_user_id == ref.platform_user_id,
                )
            )
            if row is None:
                row = UserRow(
                    platform=ref.platform,
                    platform_user_id=ref.platform_user_id,
                    created_at=to_db(now),
                    consent_at=to_db(now),
                    consent_version=consent_version,
                )
                db.add(row)
            row.username = ref.username
            row.first_name = ref.first_name
            row.consent_at = to_db(now)
            row.consent_version = consent_version
            await db.commit()
            return _user(row)

    async def delete_all_data(self, user_id: int) -> None:
        """Удалить пользователя, контакт, сессии и брифы (FR-44)."""
        async with self._factory() as db:
            await db.execute(delete(BriefRow).where(BriefRow.user_id == user_id))
            await db.execute(delete(SessionRow).where(SessionRow.user_id == user_id))
            await db.execute(delete(ContactRow).where(ContactRow.user_id == user_id))
            await db.execute(delete(UserRow).where(UserRow.id == user_id))
            await db.commit()


def _session(row: SessionRow) -> Session:
    return Session(
        id=row.id,
        user_id=row.user_id,
        status=SessionStatus(row.status),
        state=State(row.state),
        step_seq=row.step_seq,
        mode=row.mode,
        source=row.source,
        data=SessionData.model_validate_json(row.data),
        created_at=from_db(row.created_at),
        updated_at=from_db(row.updated_at),
        completed_at=from_db(row.completed_at) if row.completed_at else None,
    )


def _fill(row: SessionRow, session: Session, now: datetime) -> None:
    row.status = session.status.value
    row.state = session.state.value
    row.step_seq = session.step_seq
    row.mode = session.mode
    row.source = session.source
    row.data = session.data.model_dump_json()
    row.updated_at = to_db(now)
    row.completed_at = to_db(session.completed_at) if session.completed_at else None


class SqlSessionRepository:
    """Сессии диалога."""

    def __init__(self, factory: SessionFactory) -> None:
        self._factory = factory

    async def get_active(self, user_id: int) -> Session | None:
        async with self._factory() as db:
            row = await db.scalar(
                select(SessionRow)
                .where(SessionRow.user_id == user_id, SessionRow.status == "active")
                .order_by(SessionRow.id.desc())
                .limit(1)
            )
            return _session(row) if row else None

    async def create(self, session: Session, now: datetime) -> Session:
        async with self._factory() as db:
            row = SessionRow(user_id=session.user_id, created_at=to_db(now))
            _fill(row, session, now)
            db.add(row)
            await db.commit()
            return _session(row)

    async def save(self, session: Session, now: datetime) -> None:
        async with self._factory() as db:
            row = await db.get(SessionRow, session.id)
            if row is None:
                raise LookupError(f"сессия {session.id} не найдена")
            _fill(row, session, now)
            await db.commit()

    async def delete(self, session_id: int) -> None:
        async with self._factory() as db:
            await db.execute(delete(SessionRow).where(SessionRow.id == session_id))
            await db.commit()


class SqlBriefRepository:
    """Подтверждённые брифы."""

    def __init__(self, factory: SessionFactory) -> None:
        self._factory = factory

    async def create_confirmed(
        self,
        *,
        day: date,
        build: Callable[[str], Brief],
        session_id: int,
        user_id: int,
        now: datetime,
    ) -> Brief:
        """Следующий свободный номер за день; при гонке повторить (FR-23)."""
        prefix = f"B-{day:%y%m%d}-"
        for _ in range(_ID_ATTEMPTS):
            async with self._factory() as db:
                taken = await db.scalars(select(BriefRow.id).where(BriefRow.id.like(prefix + "%")))
                number = max((int(item.rsplit("-", 1)[1]) for item in taken), default=0) + 1
                brief = build(f"{prefix}{number:03d}")
                db.add(
                    BriefRow(
                        id=brief.brief_id,
                        session_id=session_id,
                        user_id=user_id,
                        version=brief.version,
                        brief_json=brief.model_dump_json(),
                        generated_by=brief.generated_by,
                        confirmed_at=to_db(now),
                    )
                )
                try:
                    await db.commit()
                except IntegrityError:
                    await db.rollback()
                    continue
                return brief
        raise RuntimeError("не удалось выдать ID брифа")

    async def count_confirmed_since(self, user_id: int, since: datetime) -> int:
        async with self._factory() as db:
            rows = await db.scalars(
                select(BriefRow.id).where(
                    BriefRow.user_id == user_id, BriefRow.confirmed_at >= to_db(since)
                )
            )
            return len(list(rows))

    async def get_finalize_info(self, brief_id: str) -> FinalizeInfo | None:
        async with self._factory() as db:
            brief_row = await db.get(BriefRow, brief_id)
            if brief_row is None:
                return None
            session_row = await db.get(SessionRow, brief_row.session_id)
            user_row = await db.get(UserRow, brief_row.user_id)
            contact_row = await db.get(ContactRow, brief_row.user_id)
            if session_row is None or user_row is None or contact_row is None:
                return None
            contact = Contact(
                name=contact_row.name,
                phone=contact_row.phone,
                email=contact_row.email,
                username=contact_row.username,
                preferred_method=contact_row.preferred_method,
            )
            return FinalizeInfo(
                brief=Brief.model_validate_json(brief_row.brief_json),
                contact=contact,
                source=session_row.source,
                platform=user_row.platform,
            )


class SqlContactRepository:
    """Контакты заказчиков."""

    def __init__(self, factory: SessionFactory) -> None:
        self._factory = factory

    async def save(self, user_id: int, contact: Contact, now: datetime) -> None:
        async with self._factory() as db:
            row = await db.get(ContactRow, user_id)
            if row is None:
                row = ContactRow(user_id=user_id)
                db.add(row)
            row.name = contact.name
            row.phone = contact.phone
            row.email = contact.email
            row.username = contact.username
            row.preferred_method = contact.preferred_method
            row.updated_at = to_db(now)
            await db.commit()


class SqlLLMCallLog:
    """Журнал вызовов LLM (FR-39): учёт токенов и стоимости без текстов заказчика."""

    def __init__(self, factory: SessionFactory) -> None:
        self._factory = factory

    async def record(self, call: LLMCall) -> None:
        async with self._factory() as db:
            db.add(
                LLMCallRow(
                    session_id=call.session_id,
                    purpose=call.purpose,
                    provider=call.provider,
                    model=call.model,
                    prompt_tokens=call.prompt_tokens,
                    completion_tokens=call.completion_tokens,
                    cost_rub=call.cost_rub,
                    latency_ms=call.latency_ms,
                    ok=call.ok,
                    error_kind=call.error_kind,
                    created_at=to_db(call.created_at),
                )
            )
            await db.commit()

    async def cost_since(self, since: datetime) -> float:
        async with self._factory() as db:
            total = await db.scalar(
                select(func.coalesce(func.sum(LLMCallRow.cost_rub), 0.0)).where(
                    LLMCallRow.created_at >= to_db(since)
                )
            )
            return float(total or 0.0)


class SqlLLMSwitch:
    """Флаг «LLM включена»: хранится в БД, чтобы /llm off пережил перезапуск."""

    _KEY = "llm_enabled"

    def __init__(self, factory: SessionFactory, default: bool) -> None:
        self._factory = factory
        self._default = default

    async def is_enabled(self) -> bool:
        async with self._factory() as db:
            row = await db.get(BotSettingRow, self._KEY)
            return self._default if row is None else row.value == "1"

    async def set_enabled(self, enabled: bool) -> None:
        async with self._factory() as db:
            row = await db.get(BotSettingRow, self._KEY)
            if row is None:
                row = BotSettingRow(key=self._KEY)
                db.add(row)
            row.value = "1" if enabled else "0"
            row.updated_at = to_db(datetime.now(UTC))
            await db.commit()


class SqlAuditLog:
    """Журнал событий: пользователь записывается как SHA-256 с солью (без ПДн)."""

    def __init__(self, factory: SessionFactory, salt: str) -> None:
        self._factory = factory
        self._salt = salt

    def _hash(self, ref: UserRef) -> str:
        raw = f"{self._salt}:{ref.platform}:{ref.platform_user_id}"
        return hashlib.sha256(raw.encode()).hexdigest()

    async def record(self, event: str, ref: UserRef, now: datetime) -> None:
        async with self._factory() as db:
            db.add(AuditLogRow(event=event, user_ref_hash=self._hash(ref), created_at=to_db(now)))
            await db.commit()
