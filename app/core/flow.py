"""Применение результата шага: смена состояния, служебные состояния с вызовом LLM (FR-10)."""

import logging

from app.core.context import Context
from app.core.events import UserRef
from app.core.replies import Reply
from app.core.session import Session
from app.core.steps import STEPS
from app.core.steps.common import StepResult

log = logging.getLogger(__name__)


async def apply_result(
    ctx: Context, session: Session, user: UserRef, result: StepResult
) -> list[Reply]:
    """Перейти в новое состояние и показать его prompt; последнее сохранение делает вызывающий.

    Служебное состояние (у шага есть run) сохраняется до вызова LLM: если бот
    перезапустится во время вызова, следующее событие повторит его (FR-10).
    После run переход продолжается — так ANALYZING сразу ведёт к первому вопросу.
    """
    replies = list(result.replies)
    while result.next_state is not None:
        log.info("state_changed: %s -> %s", session.state, result.next_state)
        session.state = result.next_state
        session.step_seq += 1
        step = STEPS[session.state]
        if step.run is None:
            replies += step.prompt(ctx, session, user)
            break
        await ctx.sessions.save(session, ctx.clock.now())
        result = await step.run(ctx, session)
        replies += result.replies
    return replies
