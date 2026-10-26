"""Тесты настроек (ADR-14)."""

from pathlib import Path

import pytest

from app.config import Settings, load_settings


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Пустая рабочая папка — чтобы не подхватить реальный .env."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("BOT_TOKEN", raising=False)


def _clean(monkeypatch: pytest.MonkeyPatch) -> None:
    """Оставлено для читаемости тестов: окружение уже изолировано фикстурой."""


def test_settings_read_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean(monkeypatch)
    monkeypatch.setenv("BOT_TOKEN", "123:abc")
    monkeypatch.setenv("OWNER_TELEGRAM_ID", "42")
    s = Settings()  # type: ignore[call-arg]
    assert s.bot_token.get_secret_value() == "123:abc"
    assert s.owner_telegram_id == 42
    assert s.rate_limit_per_minute == 20


def test_empty_value_means_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean(monkeypatch)
    monkeypatch.setenv("BOT_TOKEN", "123:abc")
    monkeypatch.setenv("OWNER_TELEGRAM_ID", "")
    assert Settings().owner_telegram_id is None  # type: ignore[call-arg]


def test_missing_token_exits_with_message(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        load_settings()
    assert "BOT_TOKEN" in str(exc.value)


def test_token_hidden_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean(monkeypatch)
    monkeypatch.setenv("BOT_TOKEN", "123:secret-value")
    assert "secret-value" not in repr(Settings())  # type: ignore[call-arg]
