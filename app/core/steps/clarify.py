"""Шаг CLARIFY: уточняющие вопросы по одному (FR-9)."""

from app.core.context import Context
from app.core.events import Event, TextInput, UserRef
from app.core.models import Answer
from app.core.replies import Reply, Span, TextReply
from app.core.session import Session
from app.core.states import State
from app.core.steps.common import StepResult, button, option_index, pressed, say, unexpected
from app.core.validation import ANSWER_MAX


def prompt(ctx: Context, session: Session, user: UserRef) -> list[Reply]:
    """«Вопрос N из M.», текст вопроса, варианты ответа и «Пропустить»."""
    data = session.data
    question = data.questions[data.current_question]
    header = ctx.texts.question_header.format(
        n=data.current_question + 1, total=len(data.questions)
    )
    rows = [[button(session, option, "o", index)] for index, option in enumerate(question.options)]
    rows.append([button(session, ctx.texts.skip_button, "s")])
    spans = [Span(header, bold=True), Span("\n" + question.text)]
    return [TextReply(spans, buttons=rows)]


async def handle(ctx: Context, session: Session, user: UserRef, event: Event) -> StepResult:
    """Сохранить ответ (вариант, текст или пропуск) и перейти к следующему вопросу."""
    data = session.data
    question = data.questions[data.current_question]
    payload = pressed(event)
    if payload is not None:
        if payload.action == "s":
            answer = Answer(skipped=True)
        elif (
            payload.action == "o"
            and (i := option_index(payload, len(question.options))) is not None
        ):
            answer = Answer(value=question.options[i])
        else:
            return unexpected(ctx, event)
    elif isinstance(event, TextInput) and question.allow_free_text:
        text = event.text.strip()
        if not text:
            return unexpected(ctx, event)
        if len(text) > ANSWER_MAX:
            return StepResult([say(ctx.texts.answer_too_long)])
        answer = Answer(value=text)
    else:
        return unexpected(ctx, event)

    data.answers[question.id] = answer
    if data.current_question + 1 < len(data.questions):
        data.current_question += 1
        return StepResult(next_state=State.CLARIFY)
    return StepResult(next_state=State.DEADLINE)
