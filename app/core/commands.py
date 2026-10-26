"""Команды (/start, /new, /cancel, /help, /privacy, /delete_my_data) и их подтверждения."""

from datetime import datetime

from app.core import onboarding
from app.core.context import Context
from app.core.events import CommandInput, UserRef
from app.core.payload import Payload, encode
from app.core.ports import User
from app.core.replies import Button, Reply, Span, TextReply, plain
from app.core.session import Session
from app.core.steps import STEPS
from app.core.steps.common import button, say
from app.core.validation import clean_source


def _confirm(ctx: Context, session: Session | None, text: str, kind: str) -> TextReply:
    """Вопрос «Да / Нет»; кнопки привязаны к шагу сессии или к 0, если сессии нет."""
    seq = session.step_seq if session else 0
    rows = [
        [Button(ctx.texts.confirm_yes, encode(seq, "xy", kind))],
        [Button(ctx.texts.confirm_no, encode(seq, "xn"))],
    ]
    return TextReply(plain(text), buttons=rows)


async def _start_flow(
    ctx: Context,
    user: UserRef,
    db_user: User | None,
    session: Session | None,
    source: str | None,
) -> list[Reply]:
    """Общая часть /start и /new: согласие, если его нет, иначе — продолжить или новый бриф."""
    if db_user is None or db_user.consent_version != ctx.config.consent_version:
        return onboarding.ask_consent(ctx, user, source)
    if session is not None:
        rows = [
            [button(session, ctx.texts.resume_button, "rc")],
            [button(session, ctx.texts.restart_button, "rn")],
        ]
        return [TextReply(plain(ctx.texts.resume_prompt), buttons=rows)]
    return await onboarding.begin_session(ctx, db_user, user, source)


async def handle_command(
    ctx: Context,
    user: UserRef,
    db_user: User | None,
    session: Session | None,
    command: CommandInput,
) -> list[Reply]:
    """Выполнить команду в любом состоянии диалога."""
    texts = ctx.texts
    owner = ctx.config.owner_username
    match command.name:
        case "start":
            source = clean_source(command.args.strip())
            return await _start_flow(ctx, user, db_user, session, source)
        case "new":
            if session is not None:
                return [_confirm(ctx, session, texts.new_confirm, "n")]
            return await _start_flow(ctx, user, db_user, None, None)
        case "cancel":
            if session is None:
                return [say(texts.cancel_nothing)]
            return [_confirm(ctx, session, texts.cancel_confirm, "c")]
        case "help":
            return [say(texts.help.format(owner_username=owner))]
        case "privacy":
            spans = [Span(texts.privacy)]
            if ctx.config.privacy_policy_url:
                spans.append(
                    Span("\n" + texts.privacy_link.format(url=ctx.config.privacy_policy_url))
                )
            return [TextReply(spans)]
        case "delete_my_data":
            if db_user is None:
                return [say(texts.delete_nothing)]
            return [_confirm(ctx, session, texts.delete_confirm, "d")]
        case _:
            return [say(texts.unknown_command)]


async def new_brief_pressed(
    ctx: Context, user: UserRef, db_user: User | None, session: Session | None
) -> list[Reply]:
    """Кнопка «Новый бриф» после DONE работает как /new."""
    return await handle_command(ctx, user, db_user, session, CommandInput("new"))


async def handle_confirmation(
    ctx: Context,
    user: UserRef,
    db_user: User | None,
    session: Session | None,
    payload: Payload,
) -> list[Reply]:
    """Кнопки rc / rn (продолжить или начать заново) и xy / xn (подтверждение опасных команд)."""
    texts = ctx.texts
    now = ctx.clock.now()
    if payload.action == "rc" and session is not None:
        return await _show_current(ctx, user, session)
    if payload.action == "rn" and db_user is not None:
        return await onboarding.begin_session(
            ctx, db_user, user, session.source if session else None
        )
    if payload.action == "xn":
        replies: list[Reply] = [say(texts.keep_going)]
        if session is not None:
            replies += await _show_current(ctx, user, session)
        return replies
    if payload.action == "xy":
        return await _confirmed(ctx, user, db_user, session, payload.arg, now)
    return []


async def _show_current(ctx: Context, user: UserRef, session: Session) -> list[Reply]:
    """Повторить текущий шаг; step_seq растёт, чтобы старые кнопки перестали работать."""
    session.step_seq += 1
    await ctx.sessions.save(session, ctx.clock.now())
    return STEPS[session.state].prompt(ctx, session, user)


async def _confirmed(
    ctx: Context,
    user: UserRef,
    db_user: User | None,
    session: Session | None,
    kind: str | None,
    now: datetime,
) -> list[Reply]:
    """Выполнить подтверждённое действие: отмена брифа, начать заново, удалить данные."""
    texts = ctx.texts
    if kind == "c" and session is not None and session.id is not None:
        await ctx.sessions.delete(session.id)
        return [say(texts.cancel_done)]
    if kind == "n" and db_user is not None:
        return await onboarding.begin_session(
            ctx, db_user, user, session.source if session else None
        )
    if kind == "d" and db_user is not None:
        await ctx.users.delete_all_data(db_user.id)
        await ctx.audit.record("data_deleted", user, now)
        ctx.pending_sources.pop((user.platform, user.platform_user_id), None)
        return [say(texts.delete_done)]
    return []
