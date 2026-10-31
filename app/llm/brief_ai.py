"""BriefAI: analyze, synthesize, revise с проверками, одним повтором и запасным путём (ADR-05)."""

import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.guards import MONEY, TERMS, blocking, check_analysis, clean_draft, money_or_terms
from app.core.models import Analysis, BriefDraft, BriefRevision, Question, TaskType
from app.core.ports import Clock, LLMSwitch
from app.core.question_bank import QuestionBank
from app.core.session import SessionData
from app.core.validation import strip_contacts
from app.llm.client import LLMClient, LLMResult
from app.llm.costs import BudgetGuard, LLMCall, LLMCallLog, Prices, cost_rub
from app.llm.render import render

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

NO_ANSWER = "нет ответа"
ATTEMPTS = 2  # первая попытка и один повтор после нарушения (ADR-05)

_TYPE_HINTS = {
    TaskType.CHAT_BOT: "бот: меню, анкеты, запись, уведомления, модерация",
    TaskType.AI_ASSISTANT: "ИИ-консультант, ответы по базе знаний, разбор документов",
    TaskType.AI_CONTENT: "генерация текстов, постов, изображений",
    TaskType.PARSING_MONITORING: "сбор данных с сайтов, отслеживание цен и объявлений",
    TaskType.INTEGRATION_AUTOMATION: "интеграции по API, выгрузки, отчёты, CRM",
    TaskType.DATA_ANALYTICS: "анализ данных, прогнозы, дашборды, оптимизация",
    TaskType.OTHER: "что-то другое или непонятно",
}
_VIOLATION_TEXT = {
    MONEY: "в тексте есть суммы денег",
    TERMS: "в тексте есть сроки разработки",
}


def flat_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON-схема модели без $ref и $defs: не все провайдеры понимают ссылки."""
    schema = model.model_json_schema()
    defs: dict[str, Any] = schema.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str):
                return resolve(defs[ref.rsplit("/", 1)[-1]])
            return {key: resolve(value) for key, value in node.items()}
        if isinstance(node, list):
            return [resolve(item) for item in node]
        return node

    resolved: dict[str, Any] = resolve(schema)
    return resolved


def _format_errors(error: ValidationError) -> str:
    """Кратко: где ошибка и какого рода, без значений (в них может быть текст заказчика)."""
    parts = [f"{'.'.join(str(p) for p in e['loc'])}: {e['type']}" for e in error.errors()[:5]]
    return "; ".join(parts)


class LLMBriefAI:
    """Реализация порта BriefAI поверх LLMClient."""

    def __init__(
        self,
        client: LLMClient,
        *,
        switch: LLMSwitch,
        budget: BudgetGuard,
        calls: LLMCallLog,
        bank: QuestionBank,
        clock: Clock,
        prices: Prices | None = None,
    ) -> None:
        self._client = client
        self._switch = switch
        self._budget = budget
        self._calls = calls
        self._bank = bank
        self._clock = clock
        self._prices = prices
        if prices is None:
            log.warning("llm_prices_not_set: стоимость вызовов считается как 0")

    # --- порт BriefAI ---

    async def analyze(self, description: str, *, session_id: int) -> Analysis | None:
        """Тип задачи, понимание и 3-5 вопросов (FR-14); None — перейти к шаблонному режиму."""
        messages = render(
            "analyze",
            task_types="\n".join(f"- {t.value}: {text}" for t, text in _TYPE_HINTS.items()),
            question_bank_hints=self._bank_hints(),
            description=strip_contacts(description),
        )
        return await self._generate(
            "analyze",
            messages,
            Analysis,
            temperature=0.3,
            max_tokens=1200,
            timeout_s=25,
            session_id=session_id,
            validate=self._validate_analysis,
        )

    async def synthesize(self, data: SessionData, *, session_id: int) -> BriefDraft | None:
        """Текстовая часть брифа; сроки и бюджет добавит код (FR-19). Контакты в промпт не идут."""
        client_texts = self._client_texts(data)
        messages = render(
            "synthesize",
            description=strip_contacts(data.description or ""),
            qa=self._format_qa(data),
            materials=", ".join(data.materials) or "нет",
        )

        def validate(draft: BriefDraft) -> tuple[BriefDraft, list[str]]:
            if data.task_type is not None:
                draft = draft.model_copy(update={"task_type": data.task_type})
            return clean_draft(draft, client_texts)

        return await self._generate(
            "synthesize",
            messages,
            BriefDraft,
            temperature=0.2,
            max_tokens=2000,
            timeout_s=40,
            session_id=session_id,
            validate=validate,
        )

    async def revise(
        self, draft: BriefDraft, correction: str, *, session_id: int
    ) -> BriefRevision | None:
        """Внести правку заказчика, не трогая остального (FR-22)."""
        brief_json = draft.model_dump_json()
        messages = render("revise", brief_json=brief_json, correction=strip_contacts(correction))
        client_texts = [brief_json, correction]

        def validate(revision: BriefRevision) -> tuple[BriefRevision, list[str]]:
            brief, violations = clean_draft(revision.brief, client_texts)
            changes = [strip_contacts(change) for change in revision.changes]
            for change in changes:
                violations += money_or_terms(change)
            return BriefRevision(brief=brief, changes=changes), violations

        return await self._generate(
            "revise",
            messages,
            BriefRevision,
            temperature=0.2,
            max_tokens=2000,
            timeout_s=40,
            session_id=session_id,
            validate=validate,
        )

    # --- внутреннее ---

    def _validate_analysis(self, analysis: Analysis) -> tuple[Analysis, list[str]]:
        """Проверки 11.7 и свои ID вопросов (q1…), чтобы не пересечься с ID из банка."""
        analysis, violations = check_analysis(analysis)
        questions: list[Question] = [
            q.model_copy(update={"id": f"q{i}"}) for i, q in enumerate(analysis.questions, 1)
        ]
        return analysis.model_copy(update={"questions": questions}), violations

    def _bank_hints(self) -> str:
        lines = []
        for task_type in self._bank.task_types():
            lines.append(f"{task_type.value} ({self._bank.title(task_type)}):")
            lines += [f"  - {q.text}" for q in self._bank.types[task_type].questions]
        return "\n".join(lines)

    @staticmethod
    def _format_qa(data: SessionData) -> str:
        lines = []
        for number, question in enumerate(data.questions, 1):
            answer = data.answers.get(question.id)
            text = strip_contacts(answer.value) if answer and not answer.skipped else ""
            lines.append(f"{number}. Вопрос: {question.text}\n   Ответ: {text or NO_ANSWER}")
        return "\n".join(lines) or "нет"

    @staticmethod
    def _client_texts(data: SessionData) -> list[str]:
        """Всё, что написал заказчик: числа оттуда допустимы в брифе (ТЗ 11.7, п. 2)."""
        texts = [data.description or "", data.deadline or "", data.budget or ""]
        texts += [answer.value for answer in data.answers.values() if not answer.skipped]
        return texts

    async def _generate(
        self,
        purpose: str,
        messages: list[dict[str, str]],
        model: type[T],
        *,
        temperature: float,
        max_tokens: int,
        timeout_s: float,
        session_id: int,
        validate: Callable[[T], tuple[T, list[str]]],
    ) -> T | None:
        """Вызвать модель, проверить ответ; одна повторная попытка с описанием ошибки (FR-17)."""
        if not await self._switch.is_enabled() or not await self._budget.allowed():
            return None
        schema = flat_schema(model)
        conversation = list(messages)
        for attempt in range(ATTEMPTS):
            result = await self._call(
                purpose,
                conversation,
                schema,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout_s=timeout_s,
                session_id=session_id,
            )
            if result is None:
                return None
            try:
                parsed = model.model_validate_json(result.text)
            except ValidationError as error:
                reason = f"ответ не по схеме ({_format_errors(error)})"
                kind = "format"
            else:
                fixed, violations = validate(parsed)
                problems = blocking(violations)
                if not problems:
                    return fixed
                reason = "; ".join(sorted({_VIOLATION_TEXT[v] for v in problems}))
                kind = "guard"
            # В лог — только вид нарушения: текст заказчика и ответ модели туда не попадают.
            log.warning(
                "llm_output_rejected purpose=%s kind=%s attempt=%d", purpose, kind, attempt + 1
            )
            conversation = [
                *messages,
                {
                    "role": "user",
                    "content": f"Предыдущий ответ отклонён: {reason}. "
                    "Верни JSON заново, исправив ошибку.",
                },
            ]
        return None

    async def _call(
        self,
        purpose: str,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        *,
        temperature: float,
        max_tokens: int,
        timeout_s: float,
        session_id: int,
    ) -> LLMResult | None:
        """Один вызов клиента с записью в llm_calls; любая ошибка даёт None (запасной путь)."""
        started = time.monotonic()
        try:
            result = await self._client.complete(
                messages,
                schema_name=purpose,
                schema=schema,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout_s=timeout_s,
            )
        except Exception as error:
            log.warning("llm_call_failed purpose=%s error=%s", purpose, type(error).__name__)
            await self._record(
                purpose,
                session_id,
                ok=False,
                latency_ms=int((time.monotonic() - started) * 1000),
                error_kind=type(error).__name__[:32],
            )
            return None
        await self._record(
            purpose,
            session_id,
            ok=True,
            latency_ms=result.latency_ms,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
        )
        return result

    async def _record(
        self,
        purpose: str,
        session_id: int,
        *,
        ok: bool,
        latency_ms: int,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        error_kind: str | None = None,
    ) -> None:
        await self._calls.record(
            LLMCall(
                session_id=session_id,
                purpose=purpose,
                provider=self._client.provider,
                model=self._client.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_rub=cost_rub(prompt_tokens, completion_tokens, self._prices),
                latency_ms=latency_ms,
                ok=ok,
                error_kind=error_kind,
                created_at=self._clock.now(),
            )
        )


class NullBriefAI:
    """ИИ без LLM: всегда «недоступна». Подставляется, если ключ или модель не заданы."""

    async def analyze(self, description: str, *, session_id: int) -> Analysis | None:
        return None

    async def synthesize(self, data: SessionData, *, session_id: int) -> BriefDraft | None:
        return None

    async def revise(
        self, draft: BriefDraft, correction: str, *, session_id: int
    ) -> BriefRevision | None:
        return None
