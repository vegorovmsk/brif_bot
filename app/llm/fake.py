"""FakeLLM: заранее заданные ответы для тестов и локального запуска без ключа (ADR-04)."""

from collections import defaultdict
from collections.abc import Callable
from typing import Any

from app.core.models import Analysis, BriefDraft, BriefRevision, Question, TaskType
from app.llm.client import LLMResult


class FakeLLM:
    """Отдаёт ответы по очереди для каждого назначения (analyze, synthesize, revise).

    Элемент очереди — JSON-текст или исключение, которое будет выброшено (CancelledError имитирует
    остановку процесса посреди вызова). Когда очередь
    пуста, ответ берётся из fallback; без него — RuntimeError (тест не ждал этого вызова).
    Все полученные сообщения сохраняются в calls: тесты проверяют, что в промпт не попали контакты.
    """

    provider = "fake"
    model = "fake-model"

    def __init__(
        self,
        responses: dict[str, list[str | BaseException]] | None = None,
        fallback: Callable[[str], str] | None = None,
    ) -> None:
        self._queues: dict[str, list[str | BaseException]] = defaultdict(list)
        for purpose, items in (responses or {}).items():
            self._queues[purpose] = list(items)
        self._fallback = fallback
        self.calls: list[tuple[str, list[dict[str, str]]]] = []

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        schema_name: str,
        schema: dict[str, Any],
        temperature: float,
        max_tokens: int,
        timeout_s: float,
    ) -> LLMResult:
        self.calls.append((schema_name, messages))
        queue = self._queues[schema_name]
        if queue:
            item = queue.pop(0)
            if isinstance(item, BaseException):
                raise item
            text = item
        elif self._fallback is not None:
            text = self._fallback(schema_name)
        else:
            raise RuntimeError(f"FakeLLM: нет ответа для {schema_name!r}")
        return LLMResult(
            text=text, prompt_tokens=100, completion_tokens=50, model=self.model, latency_ms=1
        )

    def prompts(self, purpose: str) -> list[str]:
        """Все тексты сообщений, отправленные модели для назначения (для проверок в тестах)."""
        return [m["content"] for name, msgs in self.calls if name == purpose for m in msgs]


def sample_analysis(*, is_dev_task: bool = True, task_type: TaskType = TaskType.CHAT_BOT) -> str:
    """Типовой ответ analyze: три вопроса, один с вариантами."""
    questions = [
        Question(id="q1", text="Кто будет пользоваться ботом?", options=["Клиенты", "Сотрудники"]),
        Question(id="q2", text="Какие действия бот должен выполнять?"),
        Question(id="q3", text="Куда отправлять собранные заявки?"),
    ]
    return Analysis(
        is_dev_task=is_dev_task,
        task_type=task_type,
        understanding="Нужен бот, который помогает клиентам и собирает заявки.",
        known_facts=["Нужен бот"],
        questions=questions if is_dev_task else [],
    ).model_dump_json()


def sample_draft(title: str = "Бот для приёма заявок") -> BriefDraft:
    """Типовой бриф без сумм, сроков и контактов."""
    return BriefDraft(
        title=title,
        task_type=TaskType.CHAT_BOT,
        summary="Бот принимает заявки от клиентов и передаёт их владельцу.",
        business_goal="Сократить время на приём заявок.",
        functional_requirements=["Принимать заявки", "Уведомлять владельца"],
        scope_in=["Бот в Telegram"],
        deliverables=["Работающий бот", "Инструкция"],
        acceptance_criteria=["Заявка доходит до владельца"],
    )


def sample_synthesis() -> str:
    """Типовой ответ synthesize."""
    return sample_draft().model_dump_json()


def sample_revision() -> str:
    """Типовой ответ revise."""
    return BriefRevision(
        brief=sample_draft("Бот для приёма заявок (уточнено)"),
        changes=["Название уточнено"],
    ).model_dump_json()


def canned(purpose: str) -> str:
    """Ответы для LLM_PROVIDER=fake: бот проходит весь сценарий без ключа и сети."""
    if purpose == "analyze":
        return sample_analysis()
    if purpose == "synthesize":
        return sample_synthesis()
    if purpose == "revise":
        return sample_revision()
    raise RuntimeError(f"FakeLLM: неизвестное назначение {purpose!r}")
