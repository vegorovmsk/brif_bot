"""Тест проверки живости (NFR-3)."""

import os
import time
from pathlib import Path

from app.healthcheck import is_alive


def test_missing_file_is_dead(tmp_path: Path) -> None:
    assert not is_alive(tmp_path / "nope")


def test_fresh_file_is_alive(tmp_path: Path) -> None:
    f = tmp_path / "hb"
    f.touch()
    assert is_alive(f)


def test_stale_file_is_dead(tmp_path: Path) -> None:
    f = tmp_path / "hb"
    f.touch()
    old = time.time() - 600
    os.utime(f, (old, old))
    assert not is_alive(f)
