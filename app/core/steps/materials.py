"""Шаг MATERIALS: что уже есть у заказчика (мультивыбор переключателями)."""

from app.core.context import Context
from app.core.events import Event, UserRef
from app.core.replies import Reply, TextReply, plain
from app.core.session import Session
from app.core.states import State
from app.core.steps.common import StepResult, button, option_index, pressed, unexpected


def _reply(ctx: Context, session: Session, *, edit: bool) -> TextReply:
    """Список переключателей с отметками ✅ и кнопкой «Готово»."""
    selected = session.data.materials
    rows = [
        [button(session, f"✅ {label}" if label in selected else label, "t", index)]
        for index, label in enumerate(ctx.texts.materials_options)
    ]
    rows.append([button(session, ctx.texts.materials_done_button, "d")])
    return TextReply(plain(ctx.texts.materials_q), buttons=rows, edit_in_place=edit)


def prompt(ctx: Context, session: Session, user: UserRef) -> list[Reply]:
    """Переключатели материалов."""
    return [_reply(ctx, session, edit=False)]


async def handle(ctx: Context, session: Session, user: UserRef, event: Event) -> StepResult:
    """Переключить пункт («Пока ничего» снимает остальные) или завершить выбор."""
    payload = pressed(event)
    if payload is None:
        return unexpected(ctx, event)
    if payload.action == "d":
        return StepResult(next_state=State.CONTACT_NAME)
    options = ctx.texts.materials_options
    index = option_index(payload, len(options)) if payload.action == "t" else None
    if index is None:
        return unexpected(ctx, event)

    nothing = options[-1]
    label = options[index]
    selected = session.data.materials
    if label in selected:
        selected.remove(label)
    elif label == nothing:
        selected.clear()
        selected.append(label)
    else:
        if nothing in selected:
            selected.remove(nothing)
        selected.append(label)
    return StepResult([_reply(ctx, session, edit=True)])
