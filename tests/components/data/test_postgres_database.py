import pytest
from sqlalchemy import select
from sqlalchemy.orm import Mapped, mapped_column

from botspot.components.data.postgres_database import (
    Base,
    PostgresDatabaseSettings,
    dispose,
    get_engine,
    get_session,
    get_session_factory,
    initialize,
    metadata,
    setup_dispatcher,
)
from botspot.core.errors import BotspotError
from botspot.utils.internal import Singleton


@pytest.fixture(autouse=True)
def clean_singleton():
    Singleton._instances = {}
    yield
    Singleton._instances = {}


class RoundtripNote(Base):
    """App-owned model registered on the shared Alembic Base.metadata."""

    __tablename__ = "botspot_roundtrip_notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str]


class TestPostgresDatabaseSettings:
    def test_defaults_disabled(self):
        settings = PostgresDatabaseSettings()
        assert settings.enabled is False
        assert "postgresql+asyncpg://" in settings.url.get_secret_value()

    def test_env_prefix(self, monkeypatch):
        monkeypatch.setenv("BOTSPOT_POSTGRES_DATABASE_ENABLED", "true")
        monkeypatch.setenv(
            "BOTSPOT_POSTGRES_DATABASE_URL",
            "postgresql+asyncpg://u:p@host:5432/db",
        )
        settings = PostgresDatabaseSettings()
        assert settings.enabled is True
        assert settings.url.get_secret_value() == "postgresql+asyncpg://u:p@host:5432/db"


class TestInitialize:
    def test_disabled_returns_none(self):
        settings = PostgresDatabaseSettings(enabled=False)
        engine, factory = initialize(settings)
        assert engine is None
        assert factory is None


class TestRealEngine:
    @pytest.mark.asyncio
    async def test_enabled_session_roundtrip_and_dispose(self, tmp_path):
        from botspot.core.dependency_manager import DependencyManager

        db_path = tmp_path / "botspot.db"
        settings = PostgresDatabaseSettings(
            enabled=True,
            url=f"sqlite+aiosqlite:///{db_path}",
        )
        engine, factory = initialize(settings)
        assert engine is not None
        assert factory is not None

        deps = DependencyManager()
        deps.postgres_engine = engine
        deps.postgres_session_factory = factory

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with get_session() as session:
            session.add(RoundtripNote(text="hello"))
            await session.commit()

        async with get_session() as session:
            found = (await session.execute(select(RoundtripNote))).scalar_one()
            assert found.text == "hello"

        await dispose()
        assert deps._postgres_engine is None
        assert deps._postgres_session_factory is None

    def test_getters_fail_when_off(self):
        from botspot.core.dependency_manager import DependencyManager

        DependencyManager()
        with pytest.raises(BotspotError) as engine_err:
            get_engine()
        assert "PostgreSQL engine is not initialized" in engine_err.value.message
        with pytest.raises(BotspotError) as factory_err:
            get_session_factory()
        assert "PostgreSQL session factory is not initialized" in factory_err.value.message


class TestDispose:
    @pytest.mark.asyncio
    async def test_dispose_when_not_initialized(self):
        from botspot.core.dependency_manager import DependencyManager

        dm = DependencyManager()
        assert dm._postgres_engine is None
        await dispose()
        assert dm._postgres_engine is None


class TestBaseAndSetup:
    def test_base_and_metadata(self):
        assert Base is not None
        assert metadata is Base.metadata
        assert RoundtripNote.__table__ in Base.metadata.tables.values()

    def test_setup_dispatcher_registers_dispose(self):
        from aiogram import Dispatcher

        dp = Dispatcher()
        setup_dispatcher(dp)
        assert any(h.callback is dispose for h in dp.shutdown.handlers)
