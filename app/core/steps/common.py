"""Общие типы и помощники для обработчиков шагов."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import NamedTuple

from app.core.context import Context
from app.core.events import ButtonPress, Event, TextInput, UserRef
from app.core.payload import Payload, encode, parse
from app.core.replies import Button, Reply, TextReply, Toast, plain
from app.core.session import Session
from app.core.states import State


@dataclass
class StepResult:
    """Итог обработки события шагом.

    next_state: перейти в это состояние (в том числе в то же самое — например, к следующему
    вопросу): движок увеличит step_seq и покажет prompt нового состояния после replies.
    """

    replies: list[Reply] = field(default_factory=list)
    next_state: State | None = None


PromptFn = Callable[[Context, Session, UserRef], list[Reply]]
HandleFn = Callable[[Context, Session, UserRef, Event], Awaitable[StepResult]]
RunFn = Callable[[Context, Session], Awaitable[StepResult]]


class Step(NamedTuple):
    """Обработчики одного состояния: что показать и как реагировать на событие.

    run есть только у служебных состояний (ANALYZING, SYNTHESIZING): они не ждут ввода,
    а сразу вызывают LLM. Движок сохраняет сессию до run (FR-10); если бот перезапустился
    во время вызова, следующее событие заказчика повторяет run.
    """

    prompt: PromptFn
    handle: HandleFn
    run: RunFn | None = None


def session_id(session: Session) -> int:
    """ID сохранённой сессии; служебные состояния работают только после сохранения (FR-10)."""
    if session.id is None:
        raise RuntimeError("сессия без ID: её нужно сначала сохранить")
    return session.id


async def no_input(ctx: Context, session: Session, user: UserRef, event: Event) -> StepResult:
    """handle служебного состояния: движок вызывает run, а не handle, поэтому ввод не нужен."""
    return StepResult()


def no_prompt(ctx: Context, session: Session, user: UserRef) -> list[Reply]:
    """prompt служебного состояния: показывается индикатор «печатает…», текста нет."""
    return []


def say(text: str) -> TextReply:
    """Простое текстовое сообщение без кнопок."""
    return TextReply(plain(text))


def button(session: Session, label: str, action: str, arg: str | int | None = None) -> Button:
    """Кнопка с payload, привязанным к текущему шагу сессии (FR-4)."""
    return Button(label, encode(session.step_seq, action, arg))


def pressed(event: Event) -> Payload | None:
    """Разобранный payload, если событие — нажатие кнопки."""
    return parse(event.payload) if isinstance(event, ButtonPress) else None


def option_index(payload: Payload, count: int) -> int | None:
    """Индекс варианта из аргумента кнопки; None, если он не число или вне диапазона."""
    if payload.arg is None or not payload.arg.isdigit():
        return None
    index = int(payload.arg)
    return index if index < count else None


def unexpected(ctx: Context, event: Event) -> StepResult:
    """Ввод, которого шаг не ждёт: подсказка по типу события."""
    if isinstance(event, TextInput):
        return StepResult([say(ctx.texts.use_buttons)])
    if isinstance(event, ButtonPress):
        return StepResult([Toast(ctx.texts.stale_button)])
    return StepResult([say(ctx.texts.text_only)])
