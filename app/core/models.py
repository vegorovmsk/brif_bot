"""Доменные модели: тип задачи, вопросы, бриф, внутренняя оценка (ТЗ, раздел 9.1)."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator


class TaskType(StrEnum):
    """Тип задачи заказчика."""

    CHAT_BOT = "chat_bot"
    AI_ASSISTANT = "ai_assistant"
    AI_CONTENT = "ai_content"
    PARSING_MONITORING = "parsing_monitoring"
    INTEGRATION_AUTOMATION = "integration_automation"
    DATA_ANALYTICS = "data_analytics"
    OTHER = "other"


class Question(BaseModel):
    """Уточняющий вопрос заказчику: от LLM (q1) или из банка (cb1)."""

    id: str = Field(pattern=r"^[a-z]{1,2}\d{1,2}$")
    text: str = Field(min_length=10, max_length=300)
    options: list[Annotated[str, Field(max_length=40)]] = Field(default_factory=list, max_length=4)
    allow_free_text: bool = True


class Answer(BaseModel):
    """Ответ заказчика на вопрос; skipped — нажато «Пропустить»."""

    value: str = ""
    skipped: bool = False


class QAItem(BaseModel):
    """Пара «вопрос — ответ» для брифа."""

    question: str
    answer: str


class Analysis(BaseModel):
    """Ответ LLM на analyze (этап 3)."""

    is_dev_task: bool
    task_type: TaskType
    understanding: str = Field(max_length=500)
    known_facts: list[str] = Field(max_length=10)
    questions: list[Question] = Field(max_length=5)

    @model_validator(mode="after")
    def _check_question_count(self) -> "Analysis":
        if self.is_dev_task and not 3 <= len(self.questions) <= 5:
            raise ValueError("для задачи на разработку нужно 3-5 вопросов")
        return self


class BriefDraft(BaseModel):
    """Текстовая часть брифа без сроков и бюджета."""

    title: str = Field(max_length=80)
    task_type: TaskType
    summary: str = Field(max_length=800)
    business_goal: str = Field(max_length=500)
    current_situation: str | None = Field(default=None, max_length=500)
    functional_requirements: list[str] = Field(min_length=1, max_length=12)
    scope_in: list[str] = Field(min_length=1, max_length=12)
    scope_out: list[str] = Field(default_factory=list, max_length=8)
    integrations: list[str] = Field(default_factory=list, max_length=8)
    deliverables: list[str] = Field(min_length=1, max_length=8)
    acceptance_criteria: list[str] = Field(min_length=1, max_length=8)
    risks: list[str] = Field(default_factory=list, max_length=6)
    open_questions: list[str] = Field(default_factory=list, max_length=8)


class Brief(BriefDraft):
    """Бриф, который видит заказчик; сроки, бюджет и ответы добавляет код (FR-19)."""

    brief_id: str
    version: int
    deadline: str
    budget: str
    materials: list[str]
    qa: list[QAItem]
    client_comments: list[str] = Field(default_factory=list)
    generated_by: Literal["llm", "template"]
    created_at: datetime


class BriefRevision(BaseModel):
    """Ответ LLM на revise (этап 3)."""

    brief: BriefDraft
    changes: list[str] = Field(max_length=5)


class RiskFlag(StrEnum):
    """Флаги рисков во внутренней оценке (этап 5)."""

    PLATFORM_RULES = "platform_rules"
    PERSONAL_DATA = "personal_data"
    MONEY_AUTOMATION = "money_automation"
    UNCLEAR_SCOPE = "unclear_scope"
    LOW_BUDGET = "low_budget"
    THIRD_PARTY_CODE = "third_party_code"
    FOREIGN_API = "foreign_api"
    DATA_AVAILABILITY = "data_availability"


class OwnerEstimate(BaseModel):
    """Внутренняя оценка: только для владельца, заказчик её не видит (ADR-06)."""

    complexity: Literal["S", "M", "L", "XL"]
    effort_hours_min: int = Field(ge=1)
    effort_hours_max: int = Field(ge=1)
    price_rub_min: int = Field(ge=0)
    price_rub_max: int = Field(ge=0)
    stack: list[str] = Field(max_length=12)
    risk_flags: list[RiskFlag]
    risks: list[str] = Field(max_length=6)
    questions_for_call: list[str] = Field(max_length=7)
    recommendation: Literal["take", "negotiate", "decline"]
    recommendation_reason: str = Field(max_length=500)

    @model_validator(mode="after")
    def _check_ranges(self) -> "OwnerEstimate":
        if self.effort_hours_min > self.effort_hours_max:
            raise ValueError("часы: min больше max")
        if self.price_rub_min > self.price_rub_max:
            raise ValueError("цена: min больше max")
        return self
