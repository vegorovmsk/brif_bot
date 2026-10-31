"""Шаг SYNTHESIZING: LLM собирает бриф по ответам заказчика (FR-19, FR-21)."""

from app.core.context import Context
from app.core.session import Session
from app.core.states import State
from app.core.steps.common import StepResult, session_id
from app.core.template_brief import build_template_draft


async def run(ctx: Context, session: Session) -> StepResult:
    """Вызвать synthesize; при сбое — шаблонный бриф. Сроки и бюджет добавляет код, не LLM."""
    data = session.data
    draft = await ctx.ai.synthesize(data, session_id=session_id(session))
    if draft is None:
        data.brief_draft = build_template_draft(data, ctx.bank)
        data.generated_by = "template"
    else:
        data.brief_draft = draft
        data.generated_by = "llm"
    return StepResult(next_state=State.REVIEW)
