"""Шаг CHOOSE_TYPE: тип задачи кнопкой (шаблонный режим, FR-18)."""

from app.core.context import Context
from app.core.events import Event, UserRef
from app.core.replies import Reply, TextReply, plain
from app.core.session import Session
from app.core.states import State
from app.core.steps.common import StepResult, button, option_index, pressed, unexpected


def prompt(ctx: Context, session: Session, user: UserRef) -> list[Reply]:
    """Кнопки с типами задач из банка вопросов."""
    rows = [
        [button(session, ctx.bank.title(task_type), "o", index)]
        for index, task_type in enumerate(ctx.bank.task_types())
    ]
    return [TextReply(plain(ctx.texts.choose_type), buttons=rows)]


async def handle(ctx: Context, session: Session, user: UserRef, event: Event) -> StepResult:
    """Запомнить тип и взять первые вопросы банка."""
    payload = pressed(event)
    types = ctx.bank.task_types()
    index = option_index(payload, len(types)) if payload and payload.action == "o" else None
    if index is None:
        return unexpected(ctx, event)
    task_type = types[index]
    session.data.task_type = task_type
    session.data.questions = ctx.bank.questions_for(task_type, ctx.config.questions_per_brief)
    session.data.current_question = 0
    return StepResult(next_state=State.CLARIFY)
