"""Шаги REVIEW и REVISING: проверка брифа, правки и подтверждение (FR-20, FR-22, FR-33)."""

from app.core.context import Context
from app.core.events import Event, TextInput, UserRef
from app.core.models import Brief
from app.core.ports import Contact
from app.core.replies import Reply, Span, Toast
from app.core.review_pack import pack
from app.core.session import Session, SessionStatus
from app.core.states import State
from app.core.steps.common import StepResult, button, pressed, say, unexpected
from app.core.template_brief import assemble_brief, build_template_draft
from app.core.validation import REVISION_MAX

PREVIEW_ID = "B-PREVIEW"


def _preview(ctx: Context, session: Session) -> Brief:
    """Бриф для показа: до подтверждения у него ещё нет настоящего ID."""
    data = session.data
    draft = data.brief_draft or build_template_draft(data, ctx.bank)
    return assemble_brief(
        draft,
        data,
        brief_id=PREVIEW_ID,
        version=data.revisions + 1,
        created_at=ctx.clock.now(),
    )


def review_prompt(ctx: Context, session: Session, user: UserRef) -> list[Reply]:
    """Сокращённый бриф и кнопки «Всё верно» / «Исправить» (после 3 правок второй нет)."""
    texts = ctx.texts
    can_edit = session.data.revisions < ctx.config.max_revisions
    sections = [[Span(texts.review_intro, italic=True)], *ctx.review.render(_preview(ctx, session))]
    if not can_edit:
        sections.append([Span(texts.revise_limit)])
    sections.append([Span(texts.no_price, italic=True)])
    rows = [[button(session, texts.review_ok_button, "ok")]]
    if can_edit:
        rows.append([button(session, texts.review_edit_button, "ed")])
    return list(pack(sections, rows))


async def review_handle(ctx: Context, session: Session, user: UserRef, event: Event) -> StepResult:
    """«Исправить» — к правке; «Всё верно» — подтвердить бриф."""
    payload = pressed(event)
    if payload is None:
        return unexpected(ctx, event)
    if payload.action == "ed" and session.data.revisions < ctx.config.max_revisions:
        return StepResult(next_state=State.REVISING)
    if payload.action == "ok":
        return await _confirm(ctx, session)
    return StepResult([Toast(ctx.texts.stale_button)])


async def _confirm(ctx: Context, session: Session) -> StepResult:
    """Подтвердить бриф: лимит (FR-13), ID (FR-23), контакт, фоновая задача (FR-33)."""
    now = ctx.clock.now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    sent_today = await ctx.briefs.count_confirmed_since(session.user_id, day_start)
    if sent_today >= ctx.config.max_briefs_per_user_per_day:
        text = ctx.texts.limit_reached.format(owner_username=ctx.config.owner_username)
        return StepResult([say(text)])
    if session.id is None:
        raise RuntimeError("сессия без ID: её нужно сначала сохранить")

    data = session.data
    draft = data.brief_draft or build_template_draft(data, ctx.bank)
    brief = await ctx.briefs.create_confirmed(
        day=now.date(),
        build=lambda brief_id: assemble_brief(
            draft, data, brief_id=brief_id, version=data.revisions + 1, created_at=now
        ),
        session_id=session.id,
        user_id=session.user_id,
        now=now,
    )
    contact = Contact(
        name=data.contact_name or "",
        phone=data.contact_phone,
        email=data.contact_email,
        username=data.contact_username,
        preferred_method=data.contact_method or "telegram",
    )
    await ctx.contacts.save(session.user_id, contact, now)
    session.status = SessionStatus.COMPLETED
    session.completed_at = now
    await ctx.outbox.enqueue_finalize(brief.brief_id)
    return StepResult(next_state=State.DONE)


def revising_prompt(ctx: Context, session: Session, user: UserRef) -> list[Reply]:
    """Просьба написать, что поправить."""
    return [say(ctx.texts.revise_prompt)]


async def revising_handle(
    ctx: Context, session: Session, user: UserRef, event: Event
) -> StepResult:
    """Без LLM правка попадает в «Комментарии заказчика» (ТЗ, 11.8)."""
    if not isinstance(event, TextInput):
        return unexpected(ctx, event)
    text = event.text.strip()
    if not text:
        return unexpected(ctx, event)
    if len(text) > REVISION_MAX:
        return StepResult([say(ctx.texts.revise_too_long)])
    session.data.client_comments.append(text)
    session.data.revisions += 1
    return StepResult([say(ctx.texts.revise_added)], next_state=State.REVIEW)
