"""Бриф без LLM: шаблонный режим (ТЗ, FR-21) и сборка итогового брифа кодом (FR-19, FR-24)."""

from datetime import datetime

from app.core.models import Brief, BriefDraft, QAItem, TaskType
from app.core.question_bank import QuestionBank
from app.core.session import SessionData
from app.core.validation import strip_contacts

PLACEHOLDER = "Уточняется при обсуждении"
NO_ANSWER = "нет ответа"
SUMMARY_MAX = 800


def build_template_draft(data: SessionData, bank: QuestionBank) -> BriefDraft:
    """Шаблонный бриф: название по типу, суть — слова заказчика, остальное — нейтрально."""
    task_type = data.task_type or TaskType.OTHER
    skipped = [
        q.text
        for q in data.questions
        if (answer := data.answers.get(q.id)) is None or answer.skipped or not answer.value
    ]
    return BriefDraft(
        title=f"Задача: {bank.title(task_type)}",
        task_type=task_type,
        summary=strip_contacts((data.description or "").strip())[:SUMMARY_MAX] or PLACEHOLDER,
        business_goal=PLACEHOLDER,
        functional_requirements=[PLACEHOLDER],
        scope_in=[PLACEHOLDER],
        deliverables=[PLACEHOLDER],
        acceptance_criteria=[PLACEHOLDER],
        open_questions=skipped[:8],
    )


def assemble_brief(
    draft: BriefDraft,
    data: SessionData,
    *,
    brief_id: str,
    version: int,
    created_at: datetime,
) -> Brief:
    """Добавить к тексту брифа то, что заполняет код: сроки, бюджет, материалы, вопросы и ответы."""
    qa = []
    for question in data.questions:
        answer = data.answers.get(question.id)
        text = strip_contacts(answer.value) if answer and not answer.skipped else ""
        qa.append(QAItem(question=question.text, answer=text or NO_ANSWER))
    return Brief(
        **draft.model_dump(),
        brief_id=brief_id,
        version=version,
        deadline=strip_contacts(data.deadline or PLACEHOLDER),
        budget=data.budget or PLACEHOLDER,
        materials=list(data.materials),
        qa=qa,
        client_comments=[strip_contacts(c) for c in data.client_comments],
        generated_by=data.generated_by,
        created_at=created_at,
    )
