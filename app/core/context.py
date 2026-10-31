"""Зависимости и настройки, с которыми работают обработчики шагов."""

from dataclasses import dataclass, field

from app.core.events import UserRef
from app.core.ports import (
    AuditLog,
    BriefAI,
    BriefRepository,
    Clock,
    ContactRepository,
    LLMSwitch,
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
    # Числовой ID владельца в Telegram: владельческие команды и исключение из лимита (FR-13, FR-37).
    owner_telegram_id: str | None = None


def is_owner(config: EngineConfig, user: UserRef) -> bool:
    """Владелец ли это: сравниваются платформа Telegram и числовой ID."""
    return (
        config.owner_telegram_id is not None
        and user.platform == "telegram"
        and user.platform_user_id == config.owner_telegram_id
    )


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
    ai: BriefAI
    llm_switch: LLMSwitch
    # Источник из deep link, пока заказчик не нажал «Согласен»: до согласия в БД ничего не пишем.
    pending_sources: dict[tuple[str, str], str | None] = field(default_factory=dict)
