"""Упаковка брифа для проверки в сообщения до 4096 символов; кнопки — у последнего (FR-20)."""

from app.core.replies import Button, Span, TextReply

TELEGRAM_LIMIT = 4096
_SEPARATOR = Span("\n\n")


def _length(spans: list[Span]) -> int:
    return sum(len(span.text) for span in spans)


def _truncate(spans: list[Span], limit: int) -> list[Span]:
    """Обрезать фрагменты так, чтобы общая длина не превышала limit."""
    result: list[Span] = []
    left = limit
    for span in spans:
        if left <= 0:
            break
        if len(span.text) > left:
            result.append(Span(span.text[: left - 1] + "…", span.bold, span.italic, span.link))
            break
        result.append(span)
        left -= len(span.text)
    return result


def pack(
    sections: list[list[Span]],
    buttons: list[list[Button]],
    limit: int = TELEGRAM_LIMIT,
) -> list[TextReply]:
    """Разбить разделы по сообщениям, не разрывая раздел; кнопки получает последнее сообщение."""
    messages: list[list[Span]] = []
    current: list[Span] = []
    for section in sections:
        section = _truncate(section, limit)
        extra = len(_SEPARATOR.text) if current else 0
        if current and _length(current) + extra + _length(section) > limit:
            messages.append(current)
            current = []
        if current:
            current = [*current, _SEPARATOR, *section]
        else:
            current = list(section)
    if current:
        messages.append(current)
    return [
        TextReply(spans=spans, buttons=buttons if index == len(messages) - 1 else [])
        for index, spans in enumerate(messages)
    ]
