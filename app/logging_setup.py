"""Логирование: structlog, JSON в prod, читаемый вывод в dev, маскирование ПДн (NFR-7, ADR-07)."""

import logging
import re
from collections.abc import MutableMapping
from typing import Any

import structlog

_PHONE_RE = re.compile(
    r"(?<![\w+])(?:\+7|8)[\s\-()]*\d{3}[\s\-()]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}(?!\d)"
)
_EMAIL_RE = re.compile(r"([\w.+-]{1,2})[\w.+-]*@([\w-]+(?:\.[\w-]+)+)")


def mask_text(text: str) -> str:
    """Замаскировать телефоны и email в строке."""
    text = _PHONE_RE.sub("+7***", text)
    return _EMAIL_RE.sub(r"\1***@\2", text)


def _mask_value(value: Any) -> Any:
    if isinstance(value, str):
        return mask_text(value)
    if isinstance(value, dict):
        return {k: _mask_value(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_mask_value(v) for v in value]
    return value


def mask_pii(
    logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Процессор structlog: маскирует телефоны и email во всех полях события."""
    for key, value in event_dict.items():
        event_dict[key] = _mask_value(value)
    return event_dict


def setup_logging(env: str) -> None:
    """Настроить structlog и перенаправить через него логи стандартного logging (aiogram)."""
    shared: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.format_exc_info,
        mask_pii,
    ]
    renderer: Any = (
        structlog.processors.JSONRenderer(ensure_ascii=False)
        if env == "prod"
        else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    handler = logging.StreamHandler()
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared,
            processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
        )
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
