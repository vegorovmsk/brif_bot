"""ORM-модели SQLAlchemy 2 (ТЗ, 9.2). Время хранится в UTC без часового пояса."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Базовый класс таблиц."""


class UserRow(Base):
    """Пользователь, давший согласие."""

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("platform", "platform_user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(16))
    platform_user_id: Mapped[str] = mapped_column(String(64))
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    consent_at: Mapped[datetime] = mapped_column(DateTime)
    consent_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class ContactRow(Base):
    """Контакт заказчика: все ПДн — здесь (ADR-07)."""

    __tablename__ = "contacts"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(128))
    phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(254))
    username: Mapped[str | None] = mapped_column(String(64))
    preferred_method: Mapped[str] = mapped_column(String(16))
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class SessionRow(Base):
    """Сессия диалога; data — JSON с SessionData."""

    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_user_status", "user_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(24))
    step_seq: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(16))
    source: Mapped[str | None] = mapped_column(String(64))
    data: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)


class BriefRow(Base):
    """Подтверждённый бриф. Отметки *_at — шаги фоновой задачи finalize_brief (этап 5)."""

    __tablename__ = "briefs"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    brief_json: Mapped[str] = mapped_column(Text)
    generated_by: Mapped[str] = mapped_column(String(16))
    estimate_json: Mapped[str | None] = mapped_column(Text)
    docx_path: Mapped[str | None] = mapped_column(String(255))
    confirmed_at: Mapped[datetime] = mapped_column(DateTime)
    estimate_done_at: Mapped[datetime | None] = mapped_column(DateTime)
    owner_notified_at: Mapped[datetime | None] = mapped_column(DateTime)
    sheet_row_added_at: Mapped[datetime | None] = mapped_column(DateTime)


class AuditLogRow(Base):
    """Журнал без ПДн: пользователь — только хеш."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event: Mapped[str] = mapped_column(String(32))
    user_ref_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime)
