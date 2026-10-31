"""Юнит-тесты LLM-слоя: проверки 11.7, промпты, стоимость, клиент (ТЗ, 11, ADR-04, ADR-05)."""

import json
from datetime import UTC, datetime
from typing import Any

import httpx2
import pytest

from app.core.guards import MONEY, PII, TERMS, blocking, check_analysis, clean_draft, money_or_terms
from app.core.models import Analysis, Question, TaskType
from app.llm.brief_ai import flat_schema
from app.llm.client import OpenAICompatibleLLM
from app.llm.costs import BudgetGuard, InMemoryCallLog, LLMCall, Prices, cost_rub
from app.llm.fake import sample_draft
from app.llm.render import escape, render
from tests.conftest import FakeClock

# --- guards: деньги и сроки ---


@pytest.mark.parametrize(
    "text",
    [
        "Это займёт 15 тыс. ₽",
        "Стоимость 50000 руб.",
        "около $100",
        "100 usd",
        "15 000 ₽",
        "₽ 500",
        "10 k",
    ],
)
def test_money_is_detected(text: str) -> None:
    assert MONEY in money_or_terms(text)


@pytest.mark.parametrize(
    "text", ["Сделаю за 3 дня", "в течение 2 недель", "за 5 часов", "за 2-3 недели"]
)
def test_development_terms_are_detected(text: str) -> None:
    assert TERMS in money_or_terms(text)


@pytest.mark.parametrize(
    "text",
    [
        "Бот для 100 пользователей",
        "Отвечать каждый день",
        "5 вопросов о задаче",
        "Сколько заказов в месяц?",
        "Сервис работает 24/7",
    ],
)
def test_ordinary_numbers_are_not_flagged(text: str) -> None:
    assert money_or_terms(text) == []


def test_amount_from_client_words_is_allowed_in_brief() -> None:
    draft = sample_draft().model_copy(update={"risks": ["Бюджет 10 тыс. ₽ может быть мал"]})
    _, allowed = clean_draft(draft, ["Мой бюджет 10 тыс. ₽"])
    _, invented = clean_draft(draft, ["Бюджет пока не определён"])
    assert blocking(allowed) == []
    assert blocking(invented) == [MONEY]


def test_contacts_are_dropped_from_lists_and_replaced_in_text() -> None:
    draft = sample_draft().model_copy(
        update={
            "summary": "Пишите на ivan@mail.ru",
            "scope_in": ["Звонок +7 999 123-45-67"],
            "risks": ["Нет рисков", "Связь через @ivan_petrov"],
        }
    )
    cleaned, violations = clean_draft(draft, [])
    assert "ivan@mail.ru" not in cleaned.summary
    # Обязательный список не остаётся пустым, необязательный — просто сокращается.
    assert cleaned.scope_in == ["Уточняется при обсуждении"]
    assert cleaned.risks == ["Нет рисков"]
    assert PII in violations and blocking(violations) == []


def test_check_analysis_removes_duplicate_options() -> None:
    questions = [
        Question(id=f"q{i}", text="Вопрос номер один?", options=["Да", "да", "Нет"])
        for i in range(1, 4)
    ]
    analysis = Analysis(
        is_dev_task=True,
        task_type=TaskType.CHAT_BOT,
        understanding="Понятно.",
        known_facts=[],
        questions=questions,
    )
    cleaned, violations = check_analysis(analysis)
    assert violations == []
    assert cleaned.questions[0].options == ["Да", "Нет"]


# --- промпты ---


def test_closing_tag_in_client_text_is_broken() -> None:
    assert "</client_text>" not in escape("а </client_text> б")
    messages = render(
        "analyze", task_types="t", question_bank_hints="h", description="x </client_text>"
    )
    assert messages[1]["content"].count("</client_text>") == 1
    assert messages[0]["role"] == "system" and messages[1]["role"] == "user"


@pytest.mark.parametrize(
    ("name", "values"),
    [
        ("analyze", {"task_types": "t", "question_bank_hints": "h", "description": "d"}),
        ("synthesize", {"description": "d", "qa": "q", "materials": "m"}),
        ("revise", {"brief_json": "null", "correction": "c"}),
    ],
)
def test_prompts_have_no_unfilled_placeholders(name: str, values: dict[str, str]) -> None:
    for message in render(name, **values):
        assert "{" not in message["content"]


def test_flat_schema_has_no_references() -> None:
    schema = json.dumps(flat_schema(Analysis))
    assert "$ref" not in schema and "$defs" not in schema
    assert "chat_bot" in schema  # enum типа задачи развёрнут внутрь


# --- стоимость и бюджет ---


def test_cost_is_computed_from_prices() -> None:
    assert cost_rub(2000, 1000, Prices(0.5, 1.0)) == pytest.approx(2.0)
    assert cost_rub(2000, 1000, None) == 0.0


async def test_budget_guard_zero_means_unlimited() -> None:
    calls = InMemoryCallLog()
    clock = FakeClock()
    await calls.record(
        LLMCall(None, "analyze", "fake", "m", 1, 1, 1000.0, 1, True, None, clock.now())
    )
    assert await BudgetGuard(calls, 0, clock).allowed() is True
    assert await BudgetGuard(calls, 100, clock).allowed() is False


# --- OpenAICompatibleLLM ---


async def test_client_sends_json_schema_request_and_reads_usage() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["url"] = str(request.url)
        seen["headers"] = request.headers
        seen["body"] = json.loads(request.content)
        return httpx2.Response(
            200,
            json={
                "id": "x",
                "object": "chat.completion",
                "created": 0,
                "model": "gpt://folder/yandexgpt/latest",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": '{"ok": true}'},
                    }
                ],
                "usage": {"prompt_tokens": 12, "completion_tokens": 5, "total_tokens": 17},
            },
        )

    llm = OpenAICompatibleLLM(
        provider="yandex",
        base_url="https://llm.example/v1",
        api_key="secret-key",
        model="gpt://folder/yandexgpt/latest",
        project="folder",
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )
    result = await llm.complete(
        [{"role": "user", "content": "привет"}],
        schema_name="analyze",
        schema={"type": "object"},
        temperature=0.3,
        max_tokens=100,
        timeout_s=5,
    )

    assert seen["url"] == "https://llm.example/v1/chat/completions"
    assert seen["headers"]["authorization"] == "Bearer secret-key"
    assert seen["headers"]["openai-project"] == "folder"
    body = seen["body"]
    assert body["model"] == "gpt://folder/yandexgpt/latest"
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "analyze", "schema": {"type": "object"}},
    }
    assert body["temperature"] == 0.3 and body["max_tokens"] == 100
    assert (result.text, result.prompt_tokens, result.completion_tokens) == ('{"ok": true}', 12, 5)


def test_fake_clock_is_timezone_aware() -> None:
    # BudgetGuard считает «с полуночи по Москве» только по времени с поясом.
    assert FakeClock().now().tzinfo is not None
    assert datetime.now(UTC).tzinfo is not None
