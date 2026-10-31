"""Проверки текстов LLM: деньги и сроки, ПДн, варианты ответов (ТЗ, 11.7, FR-17, FR-24).

Чистые функции без IO: нарушения возвращаются списком кодов, а решение (повторить вызов или
перейти к шаблону) принимает вызывающий. Тексты заказчика в нарушения не попадают.
"""

import re

from app.core.models import Analysis, BriefDraft, Question
from app.core.template_brief import PLACEHOLDER
from app.core.validation import strip_contacts

MONEY = "money"
TERMS = "terms"
PII = "pii"

_NUMBER = r"\d+(?:[ .,]\d+)*"  # без пересечения с \s*: нет катастрофического возврата
_CURRENCY = r"(?:₽|руб(?:\.|л\w*)?|р\.|тыс(?:\.|яч\w*)?|k\b|\$|usd|долл\w*|€|eur)"
_MONEY_RE = re.compile(
    rf"{_NUMBER}\s*{_CURRENCY}|(?:₽|\$|€)\s*{_NUMBER}",
    re.IGNORECASE,
)
_TERMS_RE = re.compile(
    r"(?:за|в течение)\s+\d+(?:\s*[-–—]\s*\d+)?\s*(?:дн\w*|день|недел\w*|час\w*|месяц\w*)",
    re.IGNORECASE,
)
_DIGITS_RE = re.compile(r"\d+")
_CONTACT_RE = re.compile(
    r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+|(?<![\w@])@\w{3,}|\+?\d[\d\s\-()]{8,}\d",
)


def money_or_terms(text: str) -> list[str]:
    """Суммы и сроки разработки в тексте: коды MONEY и TERMS по одному на найденное."""
    found = [MONEY for _ in _MONEY_RE.finditer(text)]
    found += [TERMS for _ in _TERMS_RE.finditer(text)]
    return found


def _numbers(text: str) -> set[str]:
    """Все числа из текста (цифры подряд, без пробелов между ними)."""
    return set(_DIGITS_RE.findall(text))


def _unsupported_amounts(text: str, client_numbers: set[str]) -> list[str]:
    """Суммы и сроки, чисел которых нет в словах заказчика: их придумала модель."""
    violations: list[str] = []
    for pattern, code in ((_MONEY_RE, MONEY), (_TERMS_RE, TERMS)):
        for match in pattern.finditer(text):
            if not _numbers(match.group()) <= client_numbers:
                violations.append(code)
    return violations


def check_analysis(analysis: Analysis) -> tuple[Analysis, list[str]]:
    """Проверить analyze: нет сумм и сроков в понимании и вопросах; варианты без дублей.

    Возвращает ответ с очищенными вариантами и список нарушений (пустой — всё в порядке).
    """
    violations = money_or_terms(analysis.understanding)
    questions: list[Question] = []
    for question in analysis.questions:
        violations += money_or_terms(question.text)
        options: list[str] = []
        for option in question.options:
            violations += money_or_terms(option)
            if option.strip().lower() not in {o.strip().lower() for o in options}:
                options.append(option)
        questions.append(question.model_copy(update={"options": options}))
    return analysis.model_copy(update={"questions": questions}), violations


def _drop_contacts(items: list[str], *, required: bool) -> tuple[list[str], bool]:
    """Убрать пункты с контактами; обязательный список не оставляем пустым."""
    kept = [item for item in items if _CONTACT_RE.search(item) is None]
    changed = len(kept) != len(items)
    if required and not kept:
        kept = [PLACEHOLDER]
    return kept, changed


def clean_draft(draft: BriefDraft, client_texts: list[str]) -> tuple[BriefDraft, list[str]]:
    """Проверить синтезированный бриф (FR-17, FR-24).

    Контакты удаляются молча (PII попадает в нарушения только для лога), а выдуманные суммы
    и сроки — это нарушение: ответ нужно сгенерировать заново. Числа, которые назвал сам
    заказчик, допустимы.
    """
    client_numbers = _numbers(" ".join(client_texts))
    violations: list[str] = []
    update: dict[str, object] = {}

    for name in ("title", "summary", "business_goal", "current_situation"):
        value = getattr(draft, name)
        if value is None:
            continue
        violations += _unsupported_amounts(value, client_numbers)
        cleaned = strip_contacts(value)
        if cleaned != value:
            violations.append(PII)
            update[name] = cleaned

    list_fields = {
        "functional_requirements": True,
        "scope_in": True,
        "scope_out": False,
        "integrations": False,
        "deliverables": True,
        "acceptance_criteria": True,
        "risks": False,
        "open_questions": False,
    }
    for name, required in list_fields.items():
        items: list[str] = getattr(draft, name)
        for item in items:
            violations += _unsupported_amounts(item, client_numbers)
        kept, changed = _drop_contacts(items, required=required)
        if changed:
            violations.append(PII)
            update[name] = kept

    return draft.model_copy(update=update), violations


def blocking(violations: list[str]) -> list[str]:
    """Нарушения, из-за которых нужна повторная генерация: деньги и сроки. ПДн чистятся сами."""
    return [v for v in violations if v in (MONEY, TERMS)]
