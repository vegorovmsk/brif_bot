"""Шаг DEADLINE: желаемый срок результата (его спрашивает код, а не LLM — FR-16)."""

from app.core.context import Context
from app.core.events import Event, TextInput, UserRef
from app.core.replies import Reply, TextReply, plain
from app.core.session import Session
from app.core.states import State
from app.core.steps.common import StepResult, button, option_index, pressed, say, unexpected
from app.core.validation import DEADLINE_MAX


def prompt(ctx: Context, session: Session, user: UserRef) -> list[Reply]:
    """Варианты срока; последний — «Своя дата»."""
    rows = [
        [button(session, label, "o", index)]
        for index, label in enumerate(ctx.texts.deadline_options)
    ]
    return [TextReply(plain(ctx.texts.deadline_q), buttons=rows)]


async def handle(ctx: Context, session: Session, user: UserRef, event: Event) -> StepResult:
    """Выбор срока кнопкой или своя формулировка текстом после «Своя дата»."""
    options = ctx.texts.deadline_options
    data = session.data
    payload = pressed(event)
    if payload is not None:
        index = option_index(payload, len(options)) if payload.action == "o" else None
        if index is None:
            return unexpected(ctx, event)
        if index == len(options) - 1:
            data.awaiting_custom_deadline = True
            return StepResult([say(ctx.texts.deadline_custom_prompt)])
        data.deadline = options[index]
    elif isinstance(event, TextInput) and data.awaiting_custom_deadline:
        text = event.text.strip()
        if not text:
            return unexpected(ctx, event)
        if len(text) > DEADLINE_MAX:
            return StepResult([say(ctx.texts.deadline_too_long)])
        data.deadline = text
    else:
        return unexpected(ctx, event)
    data.awaiting_custom_deadline = False
    return StepResult(next_state=State.BUDGET)
