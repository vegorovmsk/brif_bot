"""Payload кнопок: `<step_seq>:<действие>[:<аргумент>]`, только ASCII, до 64 байт (ТЗ, 6.5)."""

import re
from dataclasses import dataclass

MAX_PAYLOAD_BYTES = 64
_PAYLOAD_RE = re.compile(r"^(\d{1,9}):([a-z]{1,4})(?::([A-Za-z0-9_-]{1,20}))?$")

# Действия кнопок; m — выбор способа связи (дополнение к таблице 6.5).
KNOWN_ACTIONS = frozenset(
    {"cy", "cn", "o", "s", "t", "d", "m", "ok", "ed", "rc", "rn", "xy", "xn", "nw", "fin", "dl"}
)


@dataclass(frozen=True)
class Payload:
    """Разобранный payload."""

    seq: int
    action: str
    arg: str | None = None


def encode(seq: int, action: str, arg: str | int | None = None) -> str:
    """Собрать payload; ошибка, если формат или длина нарушены."""
    text = f"{seq}:{action}" if arg is None else f"{seq}:{action}:{arg}"
    if len(text.encode("ascii")) > MAX_PAYLOAD_BYTES or _PAYLOAD_RE.match(text) is None:
        raise ValueError(f"недопустимый payload: {text!r}")
    return text


def parse(text: str) -> Payload | None:
    """Строго разобрать payload; неизвестный формат или действие — None."""
    if not text.isascii() or len(text) > MAX_PAYLOAD_BYTES:
        return None
    match = _PAYLOAD_RE.match(text)
    if match is None or match.group(2) not in KNOWN_ACTIONS:
        return None
    return Payload(seq=int(match.group(1)), action=match.group(2), arg=match.group(3))
