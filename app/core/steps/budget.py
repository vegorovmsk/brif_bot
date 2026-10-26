"""Шаг BUDGET: бюджет, который рассматривает заказчик."""

from app.core.context import Context
from app.core.events import Event, UserRef
from app.core.replies import Reply, TextReply, plain
from app.core.session import Session
from app.core.states import State
from app.core.steps.common import StepResult, button, option_index, pressed, unexpected


def prompt(ctx: Context, session: Session, user: UserRef) -> list[Reply]:
    """Варианты бюджета, включая «Не знаю — нужна оценка»."""
    rows = [
        [button(session, label, "o", index)] for index, label in enumerate(ctx.texts.budget_options)
    ]
    return [TextReply(plain(ctx.texts.budget_q), buttons=rows)]


async def handle(ctx: Context, session: Session, user: UserRef, event: Event) -> StepResult:
    """Запомнить выбранный вариант бюджета."""
    payload = pressed(event)
    options = ctx.texts.budget_options
    index = option_index(payload, len(options)) if payload and payload.action == "o" else None
    if index is None:
        return unexpected(ctx, event)
    session.data.budget = options[index]
    return StepResult(next_state=State.MATERIALS)
