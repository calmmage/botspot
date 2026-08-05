"""PostgreSQL data plugin: async SQLAlchemy engine + session factory.

Env:
  BOTSPOT_POSTGRES_DATABASE_ENABLED=true
  BOTSPOT_POSTGRES_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/dbname

Usage in handlers:
  from botspot.components.data.postgres_database import get_session

  async with get_session() as session:
      ...

Alembic (app-owned migrations; Botspot ships no app tables):
  # alembic/env.py
  from botspot.components.data.postgres_database import Base
  from myapp import models  # noqa: F401 — register models on Base.metadata
  target_metadata = Base.metadata
  # Use the same URL (asyncpg driver works with Alembic async template).
"""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncIterator, Optional, Tuple

from pydantic import SecretStr
from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine  # noqa: F401
    from sqlalchemy.ext.asyncio import AsyncSession  # noqa: F401
    from sqlalchemy.ext.asyncio import async_sessionmaker

logger = get_logger()

try:
    from sqlalchemy.orm import DeclarativeBase

    class Base(DeclarativeBase):
        """Declarative base for consuming-bot models. Botspot defines no tables."""

except ImportError:  # pragma: no cover - optional until enabled
    Base = None  # type: ignore[misc, assignment]


class PostgresDatabaseSettings(BaseSettings):
    enabled: bool = False
    url: SecretStr = SecretStr("postgresql+asyncpg://localhost:5432/postgres")

    class Config:
        env_prefix = "BOTSPOT_POSTGRES_DATABASE_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


def get_engine() -> "AsyncEngine":
    """Get async SQLAlchemy engine from dependency manager."""
    from botspot.core.dependency_manager import get_dependency_manager

    engine = get_dependency_manager().postgres_engine
    if engine is None:
        raise RuntimeError(
            "PostgreSQL engine is not initialized. "
            "Enable with BOTSPOT_POSTGRES_DATABASE_ENABLED=true."
        )
    return engine


def get_session_factory() -> "async_sessionmaker[AsyncSession]":
    """Get async_sessionmaker from dependency manager."""
    from botspot.core.dependency_manager import get_dependency_manager

    factory = get_dependency_manager().postgres_session_factory
    if factory is None:
        raise RuntimeError(
            "PostgreSQL session factory is not initialized. "
            "Enable with BOTSPOT_POSTGRES_DATABASE_ENABLED=true."
        )
    return factory


@asynccontextmanager
async def get_session() -> AsyncIterator["AsyncSession"]:
    """Yield an AsyncSession; caller commits/rollbacks as needed."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


def initialize(
    settings: PostgresDatabaseSettings,
) -> Tuple[Optional["AsyncEngine"], Optional["async_sessionmaker[AsyncSession]"]]:
    """Create async engine and session factory, or (None, None) if disabled."""
    if not settings.enabled:
        logger.info("PostgreSQL is disabled")
        return None, None

    try:
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    except ImportError:
        logger.error("sqlalchemy is not installed. Install with: uv add 'sqlalchemy[asyncio]'")
        raise ImportError(
            "sqlalchemy package is not installed. "
            "Run \"uv add 'sqlalchemy[asyncio]' asyncpg\" or equivalent"
        )

    try:
        import asyncpg  # noqa: F401
    except ImportError:
        logger.error("asyncpg is not installed. Install with: uv add asyncpg")
        raise ImportError("asyncpg package is not installed. Run 'uv add asyncpg' or equivalent")

    url = settings.url.get_secret_value()
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    logger.info("PostgreSQL async engine initialized")
    return engine, session_factory


async def dispose() -> None:
    """Dispose the async engine and clear dependency manager refs."""
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    engine = getattr(deps, "_postgres_engine", None)
    if engine is None:
        logger.info("PostgreSQL dispose skipped (not initialized)")
        return

    await engine.dispose()
    deps._postgres_engine = None
    deps._postgres_session_factory = None
    logger.info("PostgreSQL engine disposed")


def setup_dispatcher(dp) -> None:
    """Register clean async disposal on bot shutdown."""
    dp.shutdown.register(dispose)


# Public Alembic surface
metadata = getattr(Base, "metadata", None)

__all__ = [
    "Base",
    "metadata",
    "PostgresDatabaseSettings",
    "initialize",
    "dispose",
    "setup_dispatcher",
    "get_engine",
    "get_session_factory",
    "get_session",
]
