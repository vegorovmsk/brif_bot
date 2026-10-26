"""Сокращённый бриф для проверки в чате: разделы 1, 4, 5, 10, 12 (ТЗ, 10.9)."""

from app.core.models import Brief
from app.core.replies import Span

REVIEW_FUNCTIONS_LIMIT = 5


def _heading(text: str) -> Span:
    return Span(text, bold=True)


def _bullets(items: list[str]) -> str:
    return "\n".join(f"• {item}" for item in items)


class TextReviewRenderer:
    """Реализует порт ReviewRenderer: бриф -> список разделов из фрагментов текста."""

    def render(self, brief: Brief) -> list[list[Span]]:
        sections = [
            [_heading("1. Суть задачи"), Span(f"\n{brief.title}\n{brief.summary}")],
            [
                _heading("4. Что должно уметь решение"),
                Span("\n" + _bullets(brief.functional_requirements[:REVIEW_FUNCTIONS_LIMIT])),
            ],
        ]
        scope = [_heading("5. Объём работ"), Span("\nВходит:\n" + _bullets(brief.scope_in))]
        if brief.scope_out:
            scope.append(Span("\nНе входит или обсудить отдельно:\n" + _bullets(brief.scope_out)))
        sections.append(scope)
        sections.append(
            [
                _heading("10. Сроки и бюджет"),
                Span(f"\nСрок: {brief.deadline}\nБюджет: {brief.budget}"),
            ]
        )
        if brief.open_questions:
            sections.append(
                [_heading("12. Открытые вопросы"), Span("\n" + _bullets(brief.open_questions))]
            )
        return sections
