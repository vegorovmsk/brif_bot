"""Начало диалога: экран согласия (FR-3) и создание сессии (FR-13)."""

from app.core.context import Context, is_owner
from app.core.events import UserRef
from app.core.payload import encode
from app.core.ports import User
from app.core.replies import Button, Reply, TextReply, plain
from app.core.session import Session
from app.core.states import State
from app.core.steps import STEPS
from app.core.steps.common import say


def _key(user: UserRef) -> tuple[str, str]:
    return (user.platform, user.platform_user_id)


def consent_screen(ctx: Context) -> TextReply:
    """Согласие на обработку данных; кнопки не привязаны к шагу (seq=0): сессии ещё нет."""
    buttons = [
        [Button(ctx.texts.consent_agree, encode(0, "cy"))],
        [Button(ctx.texts.consent_decline, encode(0, "cn"))],
    ]
    return TextReply(plain(ctx.texts.consent), buttons=buttons)


def ask_consent(ctx: Context, user: UserRef, source: str | None) -> list[Reply]:
    """Показать согласие и запомнить источник в памяти до ответа."""
    ctx.pending_sources[_key(user)] = source
    return [consent_screen(ctx)]


async def accept_consent(ctx: Context, user: UserRef) -> list[Reply]:
    """«Согласен»: создать пользователя, записать согласие и начать бриф."""
    now = ctx.clock.now()
    source = ctx.pending_sources.pop(_key(user), None)
    db_user = await ctx.users.upsert_consented(user, ctx.config.consent_version, now)
    await ctx.audit.record("consent", user, now)
    return await begin_session(ctx, db_user, user, source)


async def decline_consent(ctx: Context, user: UserRef) -> list[Reply]:
    """«Не согласен»: ничего не сохраняем, в журнал — только хеш пользователя."""
    ctx.pending_sources.pop(_key(user), None)
    await ctx.audit.record("consent_declined", user, ctx.clock.now())
    return [say(ctx.texts.consent_declined.format(owner_username=ctx.config.owner_username))]


async def begin_session(
    ctx: Context, db_user: User, user: UserRef, source: str | None
) -> list[Reply]:
    """Новая сессия с вопроса DESCRIBE; незавершённая сессия удаляется; лимит брифов (FR-13)."""
    now = ctx.clock.now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # Владельцу лимит не нужен: ему надо проверять бота на боевом сервере (FR-13).
    if not is_owner(ctx.config, user) and await ctx.briefs.count_confirmed_since(
        db_user.id, day_start
    ) >= (ctx.config.max_briefs_per_user_per_day):
        text = ctx.texts.limit_reached.format(owner_username=ctx.config.owner_username)
        return [say(text)]
    old = await ctx.sessions.get_active(db_user.id)
    if old is not None and old.id is not None:
        await ctx.sessions.delete(old.id)
    session = await ctx.sessions.create(
        Session(user_id=db_user.id, state=State.DESCRIBE, source=source), now
    )
    return STEPS[State.DESCRIBE].prompt(ctx, session, user)
