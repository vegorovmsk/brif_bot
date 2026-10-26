"""Зависимости и настройки, с которыми работают обработчики шагов."""

from dataclasses import dataclass, field

from app.core.ports import (
    AuditLog,
    BriefRepository,
    Clock,
    ContactRepository,
    Outbox,
    ReviewRenderer,
    SessionRepository,
    UserRepository,
)
from app.core.question_bank import QuestionBank
from app.core.texts import Texts


@dataclass(frozen=True)
class EngineConfig:
    """Параметры сценария (значения берутся из Settings)."""

    owner_username: str
    consent_version: str
    privacy_policy_url: str | None = None
    max_briefs_per_user_per_day: int = 3
    max_revisions: int = 3
    questions_per_brief: int = 4


@dataclass(frozen=True)
class Context:
    """Всё нужное обработчикам: репозитории, тексты, банк вопросов, настройки."""

    users: UserRepository
    sessions: SessionRepository
    briefs: BriefRepository
    contacts: ContactRepository
    audit: AuditLog
    outbox: Outbox
    review: ReviewRenderer
    clock: Clock
    texts: Texts
    bank: QuestionBank
    config: EngineConfig
    # Источник из deep link, пока заказчик не нажал «Согласен»: до согласия в БД ничего не пишем.
    pending_sources: dict[tuple[str, str], str | None] = field(default_factory=dict)
