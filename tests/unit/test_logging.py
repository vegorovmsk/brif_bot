"""Тесты маскирования ПДн в логах (NFR-7, ADR-07)."""

import pytest

from app.logging_setup import mask_pii, mask_text


@pytest.mark.parametrize(
    "raw",
    ["+7 999 123-45-67", "8 (999) 123 45 67", "+79991234567"],
)
def test_phone_is_masked(raw: str) -> None:
    out = mask_text(f"позвонить {raw} завтра")
    assert "123" not in out
    assert "+7***" in out


def test_email_is_masked() -> None:
    assert mask_text("ivan@ya.ru") == "iv***@ya.ru"


def test_plain_text_and_brief_id_untouched() -> None:
    text = "Бриф B-261023-007 принят, 12 вопросов"
    assert mask_text(text) == text


def test_processor_masks_nested_fields() -> None:
    event = {"event": "x", "contact": {"email": "ivan@ya.ru"}, "n": 5}
    out = mask_pii(None, "info", event)
    assert out["contact"]["email"] == "iv***@ya.ru"
    assert out["n"] == 5
