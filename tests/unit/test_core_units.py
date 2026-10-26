"""Юнит-тесты чистых частей ядра: payload, валидация, конфиги, шаблонный бриф, упаковка."""

from pathlib import Path

import pytest

from app.core.models import Brief, TaskType
from app.core.payload import encode, parse
from app.core.question_bank import load_question_bank
from app.core.replies import Button, Span, TextReply
from app.core.review_pack import pack
from app.core.session import SessionData
from app.core.template_brief import PLACEHOLDER, assemble_brief, build_template_draft
from app.core.texts import load_texts
from app.core.validation import (
    clean_source,
    description_problem,
    normalize_phone,
    strip_contacts,
    validate_email,
)
from app.documents.review import TextReviewRenderer
from tests.conftest import CONFIG_DIR, FakeClock

# --- payload (ТЗ, 6.5) ---


def test_payload_roundtrip() -> None:
    assert encode(7, "o", 2) == "7:o:2"
    payload = parse("7:o:2")
    assert payload is not None and (payload.seq, payload.action, payload.arg) == (7, "o", "2")
    assert parse("3:cy") is not None


@pytest.mark.parametrize(
    "raw", ["", "cy", "x:cy", "3:zz", "3:o:", "3:o:a b", "3:o:" + "1" * 70, "3:ок", "-1:cy"]
)
def test_payload_rejects_garbage(raw: str) -> None:
    assert parse(raw) is None


def test_payload_encode_rejects_too_long() -> None:
    with pytest.raises(ValueError):
        encode(1, "o", "x" * 70)


# --- validation ---


def test_description_length_limits() -> None:
    assert description_problem("коротко") == "short"
    assert description_problem("я" * 20) is None
    assert description_problem("я" * 4000) is None
    assert description_problem("я" * 4001) == "long"
    assert description_problem(" " * 30) == "short"


def test_fr12_source_validation() -> None:
    assert clean_source("youdo_15342164") == "youdo_15342164"
    assert clean_source("a" * 64) == "a" * 64
    assert clean_source("a" * 65) is None
    assert clean_source("bad source") is None
    assert clean_source("") is None


def test_phone_normalization() -> None:
    assert normalize_phone("+7 (999) 111-22-33") == "+79991112233"
    assert normalize_phone("79991112233") == "+79991112233"
    assert normalize_phone("89991112233") == "+79991112233"
    assert normalize_phone("123") is None


def test_email_validation() -> None:
    assert validate_email(" ivan@example.com ") == "ivan@example.com"
    assert validate_email("ivan@") is None
    assert validate_email("без-собаки") is None


def test_strip_contacts() -> None:
    cleaned = strip_contacts("пишите ivan@ya.ru, +7 999 123-45-67 или @ivan_petrov. Бюджет 5000")
    assert "ivan" not in cleaned and "999" not in cleaned
    assert "Бюджет 5000" in cleaned


# --- конфиги ---


def test_real_texts_and_question_bank_are_valid() -> None:
    texts = load_texts(CONFIG_DIR / "texts.yaml")
    bank = load_question_bank(CONFIG_DIR / "question_bank.yaml")
    assert len(bank.types) == len(TaskType) == 7
    assert len(bank.questions_for(TaskType.CHAT_BOT, 4)) == 4
    assert len(bank.questions_for(TaskType.OTHER, 4)) == 3  # в банке для «Другое» только 3
    assert set(texts.commands) >= {"start", "new", "cancel", "help", "privacy", "delete_my_data"}


def test_texts_with_unknown_key_are_rejected(tmp_path: Path) -> None:
    source = (CONFIG_DIR / "texts.yaml").read_text(encoding="utf-8")
    broken = tmp_path / "texts.yaml"
    broken.write_text(source + "\nlishnij_kluch: x\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_texts(broken)


def test_question_bank_without_type_is_rejected(tmp_path: Path) -> None:
    broken = tmp_path / "bank.yaml"
    broken.write_text(
        "version: 1\ntypes:\n  other:\n    title_short: x\n    questions:\n"
        "      - {id: ot1, text: 'Что должно получиться в итоге?'}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_question_bank(broken)


# --- шаблонный бриф и упаковка (FR-19, FR-20, FR-21) ---


def make_brief(summary: str = "Описание задачи для проверки") -> Brief:
    bank = load_question_bank(CONFIG_DIR / "question_bank.yaml")
    data = SessionData(
        description=summary,
        task_type=TaskType.AI_ASSISTANT,
        questions=bank.questions_for(TaskType.AI_ASSISTANT, 2),
        deadline="Не срочно",
        budget="До 10 тыс. ₽",
        materials=["ТЗ или описание"],
    )
    draft = build_template_draft(data, bank)
    return assemble_brief(
        draft, data, brief_id="B-261026-001", version=1, created_at=FakeClock().now()
    )


def test_fr21_template_brief_uses_placeholders_and_customer_data() -> None:
    brief = make_brief()
    assert brief.generated_by == "template"
    assert brief.business_goal == PLACEHOLDER
    assert brief.deadline == "Не срочно" and brief.budget == "До 10 тыс. ₽"
    assert [item.answer for item in brief.qa] == ["нет ответа", "нет ответа"]
    assert len(brief.open_questions) == 2  # пропущенные вопросы попадают в открытые


def test_fr19_summary_is_cut_to_800_chars() -> None:
    assert len(make_brief("я" * 3000).summary) == 800


def test_fr20_pack_splits_long_review_and_buttons_on_last() -> None:
    sections = [[Span("а" * 3000)], [Span("б" * 3000)]]
    buttons = [[Button("ок", "1:ok")]]
    messages = pack(sections, buttons)
    assert len(messages) == 2
    assert [m.buttons for m in messages] == [[], buttons]
    assert all(sum(len(s.text) for s in m.spans) <= 4096 for m in messages)


def test_pack_keeps_short_review_in_one_message() -> None:
    messages = pack(TextReviewRenderer().render(make_brief()), [[Button("ок", "1:ok")]])
    assert len(messages) == 1 and isinstance(messages[0], TextReply)
    text = "".join(s.text for s in messages[0].spans)
    assert "1. Суть задачи" in text and "10. Сроки и бюджет" in text
