"""Проверки пользовательского ввода: длины, источник, телефон, email (ТЗ, FR-12, FR-27)."""

import re

import phonenumbers
from email_validator import EmailNotValidError
from email_validator import validate_email as _validate_email

DESCRIPTION_MIN = 20
DESCRIPTION_MAX = 4000
ANSWER_MAX = 1000
REVISION_MAX = 1000
NAME_MAX = 60
DEADLINE_MAX = 100

_SOURCE_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_CONTACT_PATTERNS = (
    re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),  # email
    re.compile(r"(?<![\w@])@\w{3,}"),  # @username
    re.compile(r"\+?\d[\d\s\-()]{8,}\d"),  # телефон
)
CONTACT_PLACEHOLDER = "[контакт удалён]"


def description_problem(text: str) -> str | None:
    """None, если описание подходит; иначе "short" или "long"."""
    size = len(text.strip())
    if size < DESCRIPTION_MIN:
        return "short"
    if size > DESCRIPTION_MAX:
        return "long"
    return None


def clean_source(raw: str) -> str | None:
    """Источник из deep link (FR-12): только [A-Za-z0-9_-], до 64 символов; иначе None."""
    return raw if _SOURCE_RE.match(raw) else None


def normalize_phone(raw: str) -> str | None:
    """Привести телефон к E.164; None, если номер недействителен."""
    digits = re.sub(r"[^\d+]", "", raw)
    candidates = [digits] if digits.startswith("+") else ["+" + digits, digits]
    for candidate in candidates:
        try:
            number = phonenumbers.parse(candidate, "RU")
        except phonenumbers.NumberParseException:
            continue
        if phonenumbers.is_valid_number(number):
            return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
    return None


def validate_email(raw: str) -> str | None:
    """Нормализованный email или None, если формат неверный."""
    try:
        return _validate_email(raw.strip(), check_deliverability=False).normalized
    except EmailNotValidError:
        return None


def strip_contacts(text: str) -> str:
    """Убрать из текста email, @username и телефоны: в брифе контактов быть не должно (FR-24)."""
    for pattern in _CONTACT_PATTERNS:
        text = pattern.sub(CONTACT_PLACEHOLDER, text)
    return text
