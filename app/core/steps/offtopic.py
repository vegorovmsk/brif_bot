"""Шаг OFFTOPIC: запрос не про разработку, но модель могла ошибиться (ТЗ 3.4)."""

from app.core.context import Context
from app.core.events import Event, UserRef
from app.core.replies import Reply, TextReply, plain
from app.core.session import Session
from app.core.states import State
from app.core.steps.analyzing import start_clarify
from app.core.steps.common import StepResult, button, option_index, pressed, unexpected

_OTHER, _CONTINUE = 0, 1


def prompt(ctx: Context, session: Session, user: UserRef) -> list[Reply]:
    """Пояснение и две кнопки: описать другую задачу или всё же продолжить."""
    rows = [
        [button(session, ctx.texts.offtopic_other_button, "o", _OTHER)],
        [button(session, ctx.texts.offtopic_continue_button, "o", _CONTINUE)],
    ]
    return [TextReply(plain(ctx.texts.offtopic), buttons=rows)]


async def handle(ctx: Context, session: Session, user: UserRef, event: Event) -> StepResult:
    """«Описать другую задачу» — в DESCRIBE; «Всё же продолжить» — к вопросам."""
    payload = pressed(event)
    index = option_index(payload, 2) if payload and payload.action == "o" else None
    if index is None:
        return unexpected(ctx, event)
    data = session.data
    if index == _OTHER:
        data.description = None
        data.analysis = None
        data.task_type = None
        return StepResult(next_state=State.DESCRIBE)
    start_clarify(ctx, session)
    return StepResult(next_state=State.CLARIFY)
