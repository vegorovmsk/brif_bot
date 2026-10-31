"""Хранилище этапа 3: журнал вызовов LLM и переключатель /llm."""

from datetime import timedelta

from app.llm.costs import LLMCall
from app.storage.repositories import SqlLLMCallLog, SqlLLMSwitch
from tests.conftest import World


def call(world: World, cost: float, *, ago: timedelta = timedelta()) -> LLMCall:
    return LLMCall(
        session_id=1,
        purpose="analyze",
        provider="fake",
        model="m",
        prompt_tokens=10,
        completion_tokens=5,
        cost_rub=cost,
        latency_ms=7,
        ok=True,
        error_kind=None,
        created_at=world.clock.now() - ago,
    )


async def test_cost_since_counts_only_calls_after_the_moment(world: World) -> None:
    log = SqlLLMCallLog(world.factory)
    await log.record(call(world, 1.5))
    await log.record(call(world, 2.0))
    await log.record(call(world, 100.0, ago=timedelta(days=2)))
    since = world.clock.now() - timedelta(hours=1)
    assert await log.cost_since(since) == 3.5


async def test_cost_since_is_zero_without_calls(world: World) -> None:
    assert await SqlLLMCallLog(world.factory).cost_since(world.clock.now()) == 0.0


async def test_switch_default_and_persistence(world: World) -> None:
    assert await SqlLLMSwitch(world.factory, default=True).is_enabled() is True
    assert await SqlLLMSwitch(world.factory, default=False).is_enabled() is False

    await SqlLLMSwitch(world.factory, default=True).set_enabled(False)
    # Новый объект — «перезапуск»: сохранённое значение сильнее умолчания из .env.
    assert await SqlLLMSwitch(world.factory, default=True).is_enabled() is False
    await SqlLLMSwitch(world.factory, default=True).set_enabled(True)
    assert await SqlLLMSwitch(world.factory, default=False).is_enabled() is True
