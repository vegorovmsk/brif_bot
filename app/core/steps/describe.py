"""Шаг DESCRIBE: заказчик описывает задачу своими словами."""

from app.core.context import Context
from app.core.events import Event, TextInput, UserRef
from app.core.replies import Reply
from app.core.session import Session
from app.core.states import State
from app.core.steps.common import StepResult, say, unexpected
from app.core.validation import description_problem


def prompt(ctx: Context, session: Session, user: UserRef) -> list[Reply]:
    """Просьба описать задачу."""
    return [say(ctx.texts.describe)]


async def handle(ctx: Context, session: Session, user: UserRef, event: Event) -> StepResult:
    """Принять описание 20-4000 символов; дальше ANALYZING (при сбое LLM — CHOOSE_TYPE, FR-18)."""
    if not isinstance(event, TextInput):
        return unexpected(ctx, event)
    problem = description_problem(event.text)
    if problem == "short":
        return StepResult([say(ctx.texts.describe_too_short)])
    if problem == "long":
        return StepResult([say(ctx.texts.describe_too_long)])
    session.data.description = event.text.strip()
    return StepResult(next_state=State.ANALYZING)
