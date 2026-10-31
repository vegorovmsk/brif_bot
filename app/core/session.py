"""Сессия диалога и её данные (ТЗ, 9.2 и 9.3)."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from app.core.models import Analysis, Answer, BriefDraft, Question, TaskType
from app.core.states import State


class SessionStatus(StrEnum):
    """Жизненный цикл сессии."""

    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class SessionData(BaseModel):
    """Всё, что бот узнал за сессию. Хранится в sessions.data (JSON)."""

    description: str | None = None
    analysis: Analysis | None = None
    task_type: TaskType | None = None
    questions: list[Question] = Field(default_factory=list)
    current_question: int = 0
    multi_selected: list[str] = Field(default_factory=list)  # отметки в вопросе с мультивыбором
    answers: dict[str, Answer] = Field(default_factory=dict)
    deadline: str | None = None
    budget: str | None = None
    materials: list[str] = Field(default_factory=list)
    contact_name: str | None = None
    contact_method: Literal["telegram", "phone", "email"] | None = None
    contact_username: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    brief_draft: BriefDraft | None = None
    revisions: int = 0
    last_changes: list[str] = Field(default_factory=list)
    client_comments: list[str] = Field(default_factory=list)
    delivered_channels: list[str] = Field(default_factory=list)
    awaiting_custom_deadline: bool = False
    awaiting_phone: bool = False
    # Чем собран brief_draft; нужен, чтобы в бриф попала верная пометка (FR-21).
    generated_by: Literal["llm", "template"] = "template"
    # Правка, отправленная в revise: если бот перезапустился во время вызова, вызов повторится.
    pending_correction: str | None = None


class Session(BaseModel):
    """Один проход заказчика по сценарию. step_seq растёт при каждой смене шага (FR-4)."""

    id: int | None = None
    user_id: int
    status: SessionStatus = SessionStatus.ACTIVE
    state: State = State.DESCRIBE
    step_seq: int = 1
    mode: Literal["llm", "template"] = "template"
    source: str | None = None
    data: SessionData = Field(default_factory=SessionData)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None
