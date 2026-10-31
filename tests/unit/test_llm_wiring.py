"""Сборка LLM-слоя из настроек (app/main.py): выбор провайдера без сетевых вызовов."""

from pathlib import Path

import pytest

from app.config import Settings
from app.core.question_bank import load_question_bank
from app.llm.brief_ai import LLMBriefAI, NullBriefAI
from app.llm.client import OpenAICompatibleLLM
from app.llm.costs import InMemoryCallLog
from app.llm.fake import FakeLLM
from app.main import build_brief_ai, build_llm_client
from tests.conftest import CONFIG_DIR, FakeClock


class _On:
    async def is_enabled(self) -> bool:
        return True

    async def set_enabled(self, enabled: bool) -> None:
        return None


def settings(**values: object) -> Settings:
    # _env_file=None: настоящий .env разработчика в тестах не читаем.
    return Settings(_env_file=None, bot_token="123:test", **values)  # type: ignore[arg-type]


def test_fake_provider_needs_no_key() -> None:
    assert isinstance(build_llm_client(settings(llm_provider="fake")), FakeLLM)


@pytest.mark.parametrize("values", [{}, {"llm_api_key": "k"}, {"llm_model": "m"}])
def test_missing_key_or_model_disables_llm(values: dict[str, object]) -> None:
    assert build_llm_client(settings(**values)) is None


def test_yandex_client_is_openai_compatible() -> None:
    client = build_llm_client(
        settings(llm_api_key="k", llm_model="gpt://f/yandexgpt/latest", llm_project="f")
    )
    assert isinstance(client, OpenAICompatibleLLM)
    assert client.provider == "yandex" and client.model == "gpt://f/yandexgpt/latest"


async def test_build_brief_ai_falls_back_to_null_ai(tmp_path: Path) -> None:
    bank = load_question_bank(CONFIG_DIR / "question_bank.yaml")

    async def notify(text: str) -> None:
        return None

    kwargs = {"switch": _On(), "calls": InMemoryCallLog(), "bank": bank, "clock": FakeClock()}
    off = build_brief_ai(settings(), notify=notify, **kwargs)  # type: ignore[arg-type]
    assert isinstance(off, NullBriefAI)
    assert await off.analyze("описание", session_id=1) is None

    on = build_brief_ai(settings(llm_provider="fake"), notify=notify, **kwargs)  # type: ignore[arg-type]
    assert isinstance(on, LLMBriefAI)
