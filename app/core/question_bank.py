"""Загрузка и проверка банка вопросов config/question_bank.yaml (ТЗ, приложение A)."""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

from app.core.models import Question, TaskType


class TypeEntry(BaseModel):
    """Один тип задачи: подпись для кнопки и вопросы по порядку."""

    title_short: str = Field(max_length=60)
    questions: list[Question] = Field(min_length=1)


class QuestionBank(BaseModel):
    """Банк вопросов по всем типам задач."""

    version: int
    types: dict[TaskType, TypeEntry]

    @model_validator(mode="after")
    def _all_types_present(self) -> "QuestionBank":
        missing = set(TaskType) - set(self.types)
        if missing:
            raise ValueError(f"в банке нет типов: {sorted(m.value for m in missing)}")
        return self

    def task_types(self) -> list[TaskType]:
        """Типы в порядке перечисления TaskType (для кнопок CHOOSE_TYPE)."""
        return list(TaskType)

    def title(self, task_type: TaskType) -> str:
        """Короткая подпись типа задачи."""
        return self.types[task_type].title_short

    def questions_for(self, task_type: TaskType, count: int) -> list[Question]:
        """Первые count вопросов для типа задачи (FR-18)."""
        return list(self.types[task_type].questions[:count])


def load_question_bank(path: Path) -> QuestionBank:
    """Прочитать YAML банка вопросов и проверить схему."""
    with path.open(encoding="utf-8") as file:
        return QuestionBank.model_validate(yaml.safe_load(file))
