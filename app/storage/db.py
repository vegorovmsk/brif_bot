"""Подключение к SQLite: движок с WAL и внешними ключами (ADR-03)."""

from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine


def create_engine(database_url: str) -> AsyncEngine:
    """Создать движок; каталог файла БД создаётся, на каждом соединении включаются WAL и FK."""
    path = make_url(database_url).database
    if path and path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(database_url)

    @event.listens_for(engine.sync_engine, "connect")
    def _pragmas(dbapi_connection, _record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker:  # type: ignore[type-arg]
    """Фабрика сессий SQLAlchemy; объекты не «протухают» после commit."""
    return async_sessionmaker(engine, expire_on_commit=False)
