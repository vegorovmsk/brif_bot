"""Загрузка и проверка config/texts.yaml (NFR-9, ADR-14)."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class Texts(BaseModel):
    """Все тексты для заказчика. Лишний или пропущенный ключ — ошибка при старте."""

    model_config = ConfigDict(extra="forbid")

    consent: str
    consent_agree: str
    consent_decline: str
    consent_declined: str
    describe: str
    describe_too_short: str
    describe_too_long: str
    choose_type: str
    question_header: str
    skip_button: str
    answer_too_long: str
    deadline_q: str
    deadline_options: list[str] = Field(min_length=5, max_length=5)
    deadline_custom_prompt: str
    deadline_too_long: str
    budget_q: str
    budget_options: list[str] = Field(min_length=5, max_length=5)
    materials_q: str
    materials_options: list[str] = Field(min_length=5, max_length=5)
    materials_done_button: str
    contact_name_q: str
    name_too_long: str
    contact_method_q: str
    method_telegram: str
    method_phone: str
    method_email: str
    phone_prompt: str
    phone_button: str
    phone_not_own: str
    phone_received: str
    phone_invalid: str
    phone_cancelled: str
    email_prompt: str
    email_invalid: str
    review_intro: str
    review_ok_button: str
    review_edit_button: str
    revise_prompt: str
    revise_added: str
    revise_too_long: str
    revise_limit: str
    no_price: str
    done: str
    new_brief_button: str
    stale_button: str
    busy: str
    text_only: str
    use_buttons: str
    no_session: str
    limit_reached: str
    unknown_command: str
    help: str
    privacy: str
    privacy_link: str
    resume_prompt: str
    resume_button: str
    restart_button: str
    cancel_confirm: str
    cancel_done: str
    cancel_nothing: str
    new_confirm: str
    delete_confirm: str
    delete_done: str
    delete_nothing: str
    confirm_yes: str
    confirm_no: str
    keep_going: str
    commands: dict[str, str]


def load_texts(path: Path) -> Texts:
    """Прочитать YAML с текстами и проверить схему."""
    with path.open(encoding="utf-8") as file:
        return Texts.model_validate(yaml.safe_load(file))
