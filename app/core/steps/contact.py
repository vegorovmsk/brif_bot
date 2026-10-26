"""Шаги CONTACT_NAME, CONTACT_METHOD, CONTACT_EMAIL: как обращаться и как связаться."""

from app.core.context import Context
from app.core.events import ContactShared, Event, TextInput, UserRef
from app.core.replies import Reply, TextReply, plain
from app.core.session import Session
from app.core.states import State
from app.core.steps.common import StepResult, button, pressed, say, unexpected
from app.core.template_brief import build_template_draft
from app.core.validation import NAME_MAX, normalize_phone, validate_email

_NAME_BUTTON_MAX = 40


def _finish(ctx: Context, session: Session) -> StepResult:
    """Контакты собраны: без LLM бриф строится по шаблону и сразу идёт на проверку."""
    session.data.brief_draft = build_template_draft(session.data, ctx.bank)
    return StepResult(next_state=State.REVIEW)


# --- CONTACT_NAME ---


def name_prompt(ctx: Context, session: Session, user: UserRef) -> list[Reply]:
    """Вопрос об имени; кнопка с именем из профиля, если оно есть."""
    rows = []
    if user.first_name:
        label = user.first_name[:_NAME_BUTTON_MAX]
        rows.append([button(session, label, "d")])
    return [TextReply(plain(ctx.texts.contact_name_q), buttons=rows)]


async def name_handle(ctx: Context, session: Session, user: UserRef, event: Event) -> StepResult:
    """Имя из профиля (кнопка) или текстом до 60 символов."""
    payload = pressed(event)
    if payload is not None:
        if payload.action != "d" or not user.first_name:
            return unexpected(ctx, event)
        name = user.first_name[:NAME_MAX].strip()
    elif isinstance(event, TextInput):
        name = event.text.strip()
        if not name:
            return unexpected(ctx, event)
        if len(name) > NAME_MAX:
            return StepResult([say(ctx.texts.name_too_long)])
    else:
        return unexpected(ctx, event)
    session.data.contact_name = name
    return StepResult(next_state=State.CONTACT_METHOD)


# --- CONTACT_METHOD ---


def method_prompt(ctx: Context, session: Session, user: UserRef) -> list[Reply]:
    """Способы связи; «Telegram» — только если у пользователя есть username."""
    rows = []
    if user.username:
        label = ctx.texts.method_telegram.format(username=user.username)
        rows.append([button(session, label, "m", "tg")])
    rows.append([button(session, ctx.texts.method_phone, "m", "ph")])
    rows.append([button(session, ctx.texts.method_email, "m", "em")])
    return [TextReply(plain(ctx.texts.contact_method_q), buttons=rows)]


async def method_handle(ctx: Context, session: Session, user: UserRef, event: Event) -> StepResult:
    """Выбор способа связи; телефон принимается только своим контактом (FR-27)."""
    data = session.data
    payload = pressed(event)
    if payload is not None:
        if payload.action != "m" or payload.arg not in ("tg", "ph", "em"):
            return unexpected(ctx, event)
        replies: list[Reply] = []
        if data.awaiting_phone:
            data.awaiting_phone = False
            replies.append(TextReply(plain(ctx.texts.phone_cancelled), remove_reply_keyboard=True))
        if payload.arg == "tg":
            if not user.username:
                return unexpected(ctx, event)
            data.contact_method = "telegram"
            data.contact_username = user.username
            result = _finish(ctx, session)
            result.replies = replies
            return result
        if payload.arg == "em":
            data.contact_method = "email"
            return StepResult(replies, next_state=State.CONTACT_EMAIL)
        data.contact_method = "phone"
        data.awaiting_phone = True
        replies.append(
            TextReply(
                plain(ctx.texts.phone_prompt),
                request_contact=True,
                contact_label=ctx.texts.phone_button,
            )
        )
        return StepResult(replies)

    if data.awaiting_phone and isinstance(event, ContactShared):
        if not event.is_own:
            return StepResult([say(ctx.texts.phone_not_own)])
        phone = normalize_phone(event.phone)
        if phone is None:
            return StepResult([say(ctx.texts.phone_invalid)])
        data.contact_phone = phone
        data.awaiting_phone = False
        result = _finish(ctx, session)
        result.replies = [TextReply(plain(ctx.texts.phone_received), remove_reply_keyboard=True)]
        return result
    if data.awaiting_phone and isinstance(event, TextInput):
        return StepResult([say(ctx.texts.phone_not_own)])
    return unexpected(ctx, event)


# --- CONTACT_EMAIL ---


def email_prompt(ctx: Context, session: Session, user: UserRef) -> list[Reply]:
    """Просьба написать email."""
    return [say(ctx.texts.email_prompt)]


async def email_handle(ctx: Context, session: Session, user: UserRef, event: Event) -> StepResult:
    """Проверить формат email и перейти к проверке брифа."""
    if not isinstance(event, TextInput):
        return unexpected(ctx, event)
    email = validate_email(event.text)
    if email is None:
        return StepResult([say(ctx.texts.email_invalid)])
    session.data.contact_email = email
    return _finish(ctx, session)
