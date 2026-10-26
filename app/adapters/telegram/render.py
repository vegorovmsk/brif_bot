"""Span -> HTML для Telegram; весь текст экранируется (ТЗ, 6.4 и 12.2)."""

import html

from app.core.replies import Span


def render_spans(spans: list[Span]) -> str:
    """Собрать HTML-строку: каждый фрагмент экранируется отдельно, затем оборачивается в теги."""
    parts: list[str] = []
    for span in spans:
        text = html.escape(span.text, quote=False)
        if span.bold:
            text = f"<b>{text}</b>"
        if span.italic:
            text = f"<i>{text}</i>"
        if span.link:
            text = f'<a href="{html.escape(span.link, quote=True)}">{text}</a>'
        parts.append(text)
    return "".join(parts)
