"""Исходящие ответы ядра. Форматирование — нейтральное (Span), HTML делает адаптер (ТЗ, 6.4)."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Span:
    """Фрагмент текста с форматированием."""

    text: str
    bold: bool = False
    italic: bool = False
    link: str | None = None


@dataclass(frozen=True)
class Button:
    """Кнопка. payload — до 64 байт ASCII (лимит Telegram), формат — раздел 6.5."""

    label: str
    payload: str


@dataclass(frozen=True)
class TextReply:
    """Текстовый ответ с кнопками.

    request_contact: показать reply-кнопку «Поделиться контактом» с подписью contact_label.
    edit_in_place: заменить сообщение с нажатой кнопкой, а не слать новое (переключатели).
    """

    spans: list[Span]
    buttons: list[list[Button]] = field(default_factory=list)
    request_contact: bool = False
    contact_label: str = ""
    remove_reply_keyboard: bool = False
    edit_in_place: bool = False


@dataclass(frozen=True)
class DocumentReply:
    """Файл (бриф .docx, этап 4)."""

    filename: str
    content: bytes
    caption: list[Span] = field(default_factory=list)


@dataclass(frozen=True)
class Toast:
    """Всплывающее уведомление в ответ на нажатие кнопки."""

    text: str


Reply = TextReply | DocumentReply | Toast


def plain(text: str) -> list[Span]:
    """Обычный текст одним фрагментом."""
    return [Span(text)]
