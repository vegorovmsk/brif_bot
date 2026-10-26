"""Шаг DONE: бриф подтверждён, сессия завершена."""

from app.core.context import Context
from app.core.events import Event, UserRef
from app.core.payload import encode
from app.core.replies import Button, Reply, TextReply, plain
from app.core.session import Session
from app.core.steps.common import StepResult, say


def prompt(ctx: Context, session: Session, user: UserRef) -> list[Reply]:
    """Благодарность и кнопка «Новый бриф» (payload 0:nw не привязан к шагу)."""
    text = ctx.texts.done.format(owner_username=ctx.config.owner_username)
    button = Button(ctx.texts.new_brief_button, encode(0, "nw"))
    return [TextReply(plain(text), buttons=[[button]])]


async def handle(ctx: Context, session: Session, user: UserRef, event: Event) -> StepResult:
    """Завершённая сессия событий не принимает."""
    return StepResult([say(ctx.texts.no_session)])
