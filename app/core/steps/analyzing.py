"""Шаг ANALYZING: LLM определяет тип задачи и задаёт вопросы (FR-14, ТЗ 3.2)."""

from app.core.context import Context
from app.core.models import TaskType
from app.core.replies import Reply
from app.core.session import Session
from app.core.states import State
from app.core.steps.common import StepResult, say, session_id


def start_clarify(ctx: Context, session: Session) -> None:
    """Взять вопросы для CLARIFY: от LLM, а если их нет — из банка по типу задачи."""
    data = session.data
    analysis = data.analysis
    if analysis is not None and analysis.questions:
        data.questions = list(analysis.questions)
    else:
        # Запрос не про разработку и вопросов нет: банк для типа «другое» (ТЗ 3.2, OFFTOPIC).
        if analysis is not None and not analysis.is_dev_task:
            data.task_type = TaskType.OTHER
        data.questions = ctx.bank.questions_for(
            data.task_type or TaskType.OTHER, ctx.config.questions_per_brief
        )
    data.current_question = 0
    data.answers = {}
    data.multi_selected = []


async def run(ctx: Context, session: Session) -> StepResult:
    """Вызвать analyze: успех — вопросы модели, не про разработку — OFFTOPIC, сбой — CHOOSE_TYPE."""
    data = session.data
    analysis = await ctx.ai.analyze(data.description or "", session_id=session_id(session))
    if analysis is None:
        # LLM недоступна: шаблонный режим, тип выбирается кнопкой (FR-18, ТЗ 11.8).
        session.mode = "template"
        return StepResult(next_state=State.CHOOSE_TYPE)

    session.mode = "llm"
    data.analysis = analysis
    data.task_type = analysis.task_type
    if not analysis.is_dev_task:
        return StepResult(next_state=State.OFFTOPIC)
    start_clarify(ctx, session)
    replies: list[Reply] = [
        say(ctx.texts.understanding.format(understanding=analysis.understanding))
    ]
    return StepResult(replies, next_state=State.CLARIFY)
