"""Состояния диалога (ТЗ, схема 3.1)."""

from enum import StrEnum


class State(StrEnum):
    """Шаги сценария. ANALYZING, SYNTHESIZING, REVISING вызывают LLM (этап 3)."""

    CONSENT = "consent"
    DESCRIBE = "describe"
    ANALYZING = "analyzing"
    OFFTOPIC = "offtopic"
    CHOOSE_TYPE = "choose_type"
    CLARIFY = "clarify"
    DEADLINE = "deadline"
    BUDGET = "budget"
    MATERIALS = "materials"
    CONTACT_NAME = "contact_name"
    CONTACT_METHOD = "contact_method"
    CONTACT_EMAIL = "contact_email"
    SYNTHESIZING = "synthesizing"
    REVIEW = "review"
    REVISING = "revising"
    DELIVERY = "delivery"
    DELIVERY_EMAIL = "delivery_email"
    DONE = "done"
