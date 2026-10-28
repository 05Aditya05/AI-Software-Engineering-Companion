"""Lazy async PostgreSQL engine and session helpers (Phase 9.1)."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Create the engine on first use; importing the app never connects to the DB."""
    global _engine, _session_factory
    if _engine is None:
        database_url = settings.database_url.get_secret_value()
        if not database_url:
            raise RuntimeError("DATABASE_URL must be configured before using PostgreSQL")
        if not database_url.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use the postgresql+asyncpg scheme")
        _engine = create_async_engine(database_url, pool_pre_ping=True)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a short-lived async database session."""
    get_engine()
    assert _session_factory is not None
    async with _session_factory() as session:
        yield session


async def dispose_database_engine() -> None:
    """Dispose the engine when the service shuts down, if it was initialized."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
