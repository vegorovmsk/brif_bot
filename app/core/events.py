"""Входящие события ядра: адаптер мессенджера переводит в них обновления платформы (ТЗ, 6.4)."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class UserRef:
    """Кто пишет: платформа и ID пользователя на ней."""

    platform: Literal["telegram", "vk", "max"]
    platform_user_id: str
    username: str | None
    first_name: str | None


@dataclass(frozen=True)
class TextInput:
    """Текстовое сообщение."""

    text: str


@dataclass(frozen=True)
class ButtonPress:
    """Нажатие кнопки; payload — строка формата раздела 6.5."""

    payload: str


@dataclass(frozen=True)
class ContactShared:
    """Контакт из кнопки «Поделиться». is_own: адаптер сравнил contact.user_id с отправителем."""

    phone: str
    is_own: bool


@dataclass(frozen=True)
class UnsupportedInput:
    """Голос, фото, файл, стикер и другое, что бот пока не понимает."""

    kind: str


@dataclass(frozen=True)
class CommandInput:
    """Команда: name без слэша (start, new, cancel, help, privacy, delete_my_data)."""

    name: str
    args: str = ""


Event = TextInput | ButtonPress | ContactShared | UnsupportedInput | CommandInput
