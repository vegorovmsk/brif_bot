"""Интеграционные тесты хранилища: миграции совпадают с ORM, WAL, ID брифов (FR-23)."""

from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine as create_sync_engine
from sqlalchemy import text

from app.core.models import Brief
from app.core.session import Session
from app.main import ROOT
from app.storage.tables import Base, BriefRow
from tests.conftest import World, make_user
from tests.scenario.test_scenarios import count
from tests.unit.test_core_units import make_brief


def test_alembic_head_matches_orm_models(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db_path = tmp_path / "migrated.db"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")

    engine = create_sync_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


async def test_wal_and_foreign_keys_are_enabled(world: World) -> None:
    async with world.db.connect() as conn:
        assert (await conn.execute(text("PRAGMA journal_mode"))).scalar() == "wal"
        assert (await conn.execute(text("PRAGMA foreign_keys"))).scalar() == 1


async def test_fr23_brief_ids_count_per_day(world: World) -> None:
    ctx = world.make_engine()._ctx
    now = world.clock.now()
    user = await ctx.users.upsert_consented(make_user(), "v1", now)
    session = await ctx.sessions.create(Session(user_id=user.id), now)
    assert session.id is not None

    def build(brief_id: str) -> Brief:
        return make_brief().model_copy(update={"brief_id": brief_id})

    ids = []
    for day in (date(2026, 10, 26), date(2026, 10, 26), date(2026, 10, 27)):
        brief = await ctx.briefs.create_confirmed(
            day=day, build=build, session_id=session.id, user_id=user.id, now=now
        )
        ids.append(brief.brief_id)
    assert ids == ["B-261026-001", "B-261026-002", "B-261027-001"]
    assert await count(world, BriefRow) == 3
