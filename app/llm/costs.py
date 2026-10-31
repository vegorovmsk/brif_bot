"""Стоимость вызовов LLM и дневной бюджет (FR-39, FR-40)."""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.core.ports import Clock

log = logging.getLogger(__name__)

WARN_SHARE = 0.8


@dataclass(frozen=True)
class Prices:
    """Цена за 1000 токенов в рублях (из .env по актуальному прайсу провайдера)."""

    input_per_1k: float
    output_per_1k: float


def cost_rub(prompt_tokens: int, completion_tokens: int, prices: Prices | None) -> float:
    """Стоимость вызова; без цен в .env — 0, а предупреждение пишет вызывающий один раз."""
    if prices is None:
        return 0.0
    return (
        prompt_tokens / 1000 * prices.input_per_1k + completion_tokens / 1000 * prices.output_per_1k
    )


@dataclass(frozen=True)
class LLMCall:
    """Строка таблицы llm_calls: без текстов заказчика, только учёт."""

    session_id: int | None
    purpose: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_rub: float
    latency_ms: int
    ok: bool
    error_kind: str | None
    created_at: datetime


class LLMCallLog(Protocol):
    """Журнал вызовов; реализация — в app/storage, для eval — в памяти."""

    async def record(self, call: LLMCall) -> None: ...

    async def cost_since(self, since: datetime) -> float:
        """Сумма cost_rub вызовов начиная с момента since."""
        ...


class InMemoryCallLog:
    """Журнал в памяти: для tools/eval.py, где БД не нужна."""

    def __init__(self) -> None:
        self.calls: list[LLMCall] = []

    async def record(self, call: LLMCall) -> None:
        self.calls.append(call)

    async def cost_since(self, since: datetime) -> float:
        return sum(c.cost_rub for c in self.calls if c.created_at >= since)


class BudgetGuard:
    """Дневной бюджет LLM (FR-40): на 80 % предупреждение владельцу, на 100 % — шаблонный режим.

    Расход считается по llm_calls с полуночи по Москве, поэтому в 00:00 бюджет обнуляется сам.
    Каждое оповещение уходит один раз в сутки.
    """

    def __init__(
        self,
        calls: LLMCallLog,
        daily_budget_rub: float,
        clock: Clock,
        notify: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        self._calls = calls
        self._budget = daily_budget_rub
        self._clock = clock
        self._notify = notify
        self._warned: set[tuple[str, str]] = set()

    async def allowed(self) -> bool:
        """Можно ли делать ещё вызов; бюджет 0 или меньше означает «без ограничения»."""
        if self._budget <= 0:
            return True
        now = self._clock.now()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        spent = await self._calls.cost_since(day_start)
        day = now.date().isoformat()
        if spent >= self._budget:
            await self._alert(
                ("exhausted", day),
                f"⚠️ Дневной бюджет LLM исчерпан ({spent:.0f} из {self._budget:.0f} ₽). "
                "До полуночи бот работает в шаблонном режиме.",
            )
            return False
        if spent >= self._budget * WARN_SHARE:
            await self._alert(
                ("warning", day),
                f"⚠️ Потрачено {spent:.0f} из {self._budget:.0f} ₽ дневного бюджета LLM (80 %).",
            )
        return True

    async def _alert(self, key: tuple[str, str], text: str) -> None:
        if key in self._warned:
            return
        self._warned.add(key)
        log.warning("llm_budget: %s", key[0])
        if self._notify is not None:
            try:
                await self._notify(text)
            except Exception:  # оповещение не должно ломать сценарий заказчика
                log.exception("llm_budget_notify_failed")
