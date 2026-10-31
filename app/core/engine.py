"""ConversationEngine: единственная точка входа ядра (ТЗ, 6.4, ADR-02)."""

import logging

from app.core import commands, flow, onboarding
from app.core.context import Context
from app.core.events import ButtonPress, CommandInput, Event, UserRef
from app.core.payload import parse
from app.core.ports import User
from app.core.replies import Reply, Toast
from app.core.session import Session
from app.core.steps import STEPS
from app.core.steps.common import say

log = logging.getLogger(__name__)

_CONFIRMATION_ACTIONS = frozenset({"rc", "rn", "xy", "xn"})


class ConversationEngine:
    """Обрабатывает события пользователя и возвращает ответы; платформы не знает."""

    def __init__(self, ctx: Context) -> None:
        self._ctx = ctx

    async def handle(self, user: UserRef, event: Event) -> list[Reply]:
        """Обработать событие под блокировкой на пользователя (её держит адаптер, FR-6).

        Порядок: команды в любом состоянии -> проверка шага кнопки (FR-5) ->
        обработчик текущего состояния -> сохранение сессии.
        """
        ctx = self._ctx
        db_user = await ctx.users.get(user.platform, user.platform_user_id)
        session = await ctx.sessions.get_active(db_user.id) if db_user else None

        if isinstance(event, CommandInput):
            return await commands.handle_command(ctx, user, db_user, session, event)
        if isinstance(event, ButtonPress):
            return await self._handle_button(user, db_user, session, event)
        if session is None:
            return [say(ctx.texts.no_session)]
        return await self._run_step(user, session, event)

    async def _handle_button(
        self, user: UserRef, db_user: User | None, session: Session | None, event: ButtonPress
    ) -> list[Reply]:
        ctx = self._ctx
        payload = parse(event.payload)
        if payload is None:
            log.warning("bad_payload")
            return []
        if payload.action == "nw":
            return await commands.new_brief_pressed(ctx, user, db_user, session)

        expected_seq = session.step_seq if session else 0
        if payload.seq != expected_seq:
            return [Toast(ctx.texts.stale_button)]

        if payload.action == "cy":
            return await onboarding.accept_consent(ctx, user)
        if payload.action == "cn":
            return await onboarding.decline_consent(ctx, user)
        if payload.action in _CONFIRMATION_ACTIONS:
            return await commands.handle_confirmation(ctx, user, db_user, session, payload)
        if session is None:
            return [Toast(ctx.texts.stale_button)]
        return await self._run_step(user, session, event)

    async def _run_step(self, user: UserRef, session: Session, event: Event) -> list[Reply]:
        ctx = self._ctx
        step = STEPS.get(session.state)
        if step is None:
            return [say(ctx.texts.no_session)]
        if step.run is not None:
            # Бот перезапустился посреди вызова LLM: повторяем его с сохранёнными данными (FR-10).
            result = await step.run(ctx, session)
        else:
            result = await step.handle(ctx, session, user, event)
        replies = await flow.apply_result(ctx, session, user, result)
        await ctx.sessions.save(session, ctx.clock.now())
        return replies
