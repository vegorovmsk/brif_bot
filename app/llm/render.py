"""Загрузка промптов из app/llm/prompts/*.md и безопасная подстановка текста заказчика."""

from functools import cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"
_SEPARATOR = "\n=====\n"


def escape(text: str) -> str:
    """Сломать закрывающие теги в тексте заказчика: он не должен выйти из своего тега (ТЗ 11.1)."""
    return text.replace("</", "<​/")


@cache
def _load(name: str) -> tuple[str, str]:
    """Промпт делится строкой ===== на системную часть (правила) и данные заказчика."""
    raw = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    system, _, user = raw.partition(_SEPARATOR)
    return system.strip(), user.strip()


def render(name: str, **values: str) -> list[dict[str, str]]:
    """Сообщения для модели: system — правила, user — данные. Все значения экранируются."""
    system, user = _load(name)
    safe = {key: escape(value) for key, value in values.items()}
    return [
        {"role": "system", "content": system.format(**safe)},
        {"role": "user", "content": user.format(**safe)},
    ]
