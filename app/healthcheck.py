"""Проверка живости для Docker HEALTHCHECK: файл heartbeat должен быть свежим."""

import sys
import tempfile
import time
from pathlib import Path

HEARTBEAT_PATH = Path(tempfile.gettempdir()) / "heartbeat"
MAX_AGE_SECONDS = 90


def is_alive(path: Path = HEARTBEAT_PATH, max_age: float = MAX_AGE_SECONDS) -> bool:
    """Файл существует и обновлялся не раньше max_age секунд назад."""
    try:
        return time.time() - path.stat().st_mtime < max_age
    except OSError:
        return False


if __name__ == "__main__":
    sys.exit(0 if is_alive() else 1)
