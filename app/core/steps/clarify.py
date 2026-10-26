"""Шаг CLARIFY: уточняющие вопросы по одному, с выбором одного или нескольких вариантов (FR-9)."""

from app.core.context import Context
from app.core.events import Event, TextInput, UserRef
from app.core.models import Answer, Question
from app.core.replies import Reply, Span, TextReply
from app.core.session import Session
from app.core.states import State
from app.core.steps.common import StepResult, button, option_index, pressed, say, unexpected
from app.core.validation import ANSWER_MAX


def _question_reply(ctx: Context, session: Session, *, edit: bool) -> TextReply:
    """Сообщение с вопросом; у вопроса с мультивыбором варианты — переключатели с ✅."""
    data = session.data
    question = data.questions[data.current_question]
    header = ctx.texts.question_header.format(
        n=data.current_question + 1, total=len(data.questions)
    )
    text = question.text + (f" {ctx.texts.multi_hint}" if question.multi else "")
    if question.multi:
        rows = [
            [button(session, f"✅ {option}" if option in data.multi_selected else option, "t", i)]
            for i, option in enumerate(question.options)
        ]
        rows.append([button(session, ctx.texts.multi_done_button, "d")])
    else:
        rows = [[button(session, option, "o", i)] for i, option in enumerate(question.options)]
    rows.append([button(session, ctx.texts.skip_button, "s")])
    spans = [Span(header, bold=True), Span("\n" + text)]
    return TextReply(spans, buttons=rows, edit_in_place=edit)


def prompt(ctx: Context, session: Session, user: UserRef) -> list[Reply]:
    """«Вопрос N из M.», текст вопроса, варианты ответа и «Пропустить»."""
    return [_question_reply(ctx, session, edit=False)]


def _toggle(question: Question, selected: list[str], option: str) -> None:
    """Переключить вариант; «исключающий» вариант («Ничего из этого») снимает остальные."""
    if option in selected:
        selected.remove(option)
    elif option == question.exclusive:
        selected.clear()
        selected.append(option)
    else:
        if question.exclusive in selected:
            selected.remove(question.exclusive)
        selected.append(option)


async def handle(ctx: Context, session: Session, user: UserRef, event: Event) -> StepResult:
    """Сохранить ответ (вариант, отметки, текст или пропуск) и перейти к следующему вопросу."""
    data = session.data
    question = data.questions[data.current_question]
    payload = pressed(event)
    if payload is not None:
        if payload.action == "s":
            answer = Answer(skipped=True)
        elif question.multi and payload.action == "t":
            index = option_index(payload, len(question.options))
            if index is None:
                return unexpected(ctx, event)
            _toggle(question, data.multi_selected, question.options[index])
            return StepResult([_question_reply(ctx, session, edit=True)])
        elif question.multi and payload.action == "d":
            chosen = [o for o in question.options if o in data.multi_selected]
            answer = Answer(value=", ".join(chosen)) if chosen else Answer(skipped=True)
        elif (
            not question.multi
            and payload.action == "o"
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
    data.multi_selected = []
    if data.current_question + 1 < len(data.questions):
        data.current_question += 1
        return StepResult(next_state=State.CLARIFY)
    return StepResult(next_state=State.DEADLINE)
