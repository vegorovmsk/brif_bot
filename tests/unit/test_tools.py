"""Тесты служебных скриптов этапа 2: профиль бота и проверка доступности."""

import socket
from pathlib import Path

import pytest

from tools.check_connectivity import Result, check, format_result
from tools.setup_bot_profile import LIMITS, PROFILE_PATH, load_profile


def test_bot_profile_fits_telegram_limits() -> None:
    profile = load_profile()
    assert set(profile) == set(LIMITS)
    assert all(len(profile[key]) <= limit for key, limit in LIMITS.items())


def test_bot_profile_over_limit_is_rejected(tmp_path: Path) -> None:
    source = PROFILE_PATH.read_text(encoding="utf-8").splitlines()
    broken = [line for line in source if not line.startswith("name:")]
    broken.append('name: "' + "я" * 65 + '"')
    path = tmp_path / "profile.yaml"
    path.write_text("\n".join(broken), encoding="utf-8")
    with pytest.raises(ValueError, match="name"):
        load_profile(path)


def test_check_reports_ok_for_listening_port() -> None:
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        result = check("127.0.0.1", port, tls=False, timeout=2)
    assert result.ok and result.error == ""


def test_check_reports_fail_for_closed_port() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]  # порт освобождается при выходе из with
    result = check("127.0.0.1", port, tls=False, timeout=2)
    assert not result.ok and result.error


def test_format_result_lines() -> None:
    ok = format_result(Result("a.example", 443, True, 42), "Сервис", "подсказка")
    assert ok.startswith("OK") and "42 мс" in ok
    fail = format_result(Result("a.example", 443, False, 5, "TimeoutError"), "Сервис", "подсказка")
    assert fail.startswith("FAIL") and "TimeoutError" in fail and "подсказка" in fail
