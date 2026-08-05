from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
from botspot.utils.internal import Singleton


@pytest.fixture(autouse=True)
def clean_singleton():
    Singleton._instances = {}
    yield
    Singleton._instances = {}


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

    def test_enabled_creates_engine_and_sessionmaker(self):
        settings = PostgresDatabaseSettings(
            enabled=True,
            url="postgresql+asyncpg://localhost:5432/test",
        )
        mock_engine = MagicMock()
        mock_factory = MagicMock()

        with (
            patch(
                "sqlalchemy.ext.asyncio.create_async_engine",
                return_value=mock_engine,
            ) as mock_create_engine,
            patch(
                "sqlalchemy.ext.asyncio.async_sessionmaker",
                return_value=mock_factory,
            ) as mock_sessionmaker,
            patch.dict("sys.modules", {"asyncpg": MagicMock()}),
        ):
            # ensure import path succeeds even if already installed
            engine, factory = initialize(settings)

        assert engine is mock_engine
        assert factory is mock_factory
        mock_create_engine.assert_called_once_with("postgresql+asyncpg://localhost:5432/test")
        mock_sessionmaker.assert_called_once_with(mock_engine, expire_on_commit=False)


class TestDispose:
    @pytest.mark.asyncio
    async def test_dispose_clears_engine(self):
        from botspot.core.dependency_manager import DependencyManager

        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()
        dm = DependencyManager()
        dm._postgres_engine = mock_engine
        dm._postgres_session_factory = MagicMock()

        await dispose()

        mock_engine.dispose.assert_awaited_once()
        assert dm._postgres_engine is None
        assert dm._postgres_session_factory is None

    @pytest.mark.asyncio
    async def test_dispose_when_not_initialized(self):
        from botspot.core.dependency_manager import DependencyManager

        dm = DependencyManager()
        assert dm._postgres_engine is None
        await dispose()  # no-op
        assert dm._postgres_engine is None


class TestGetters:
    def test_get_engine_success(self):
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            mock_deps = MagicMock()
            mock_engine = MagicMock()
            mock_deps.postgres_engine = mock_engine
            mock_get_deps.return_value = mock_deps

            assert get_engine() is mock_engine

    def test_get_engine_not_initialized(self):
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            mock_deps = MagicMock()
            mock_deps.postgres_engine = None
            mock_get_deps.return_value = mock_deps

            with pytest.raises(RuntimeError, match="PostgreSQL engine is not initialized"):
                get_engine()

    def test_get_session_factory_success(self):
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            mock_deps = MagicMock()
            mock_factory = MagicMock()
            mock_deps.postgres_session_factory = mock_factory
            mock_get_deps.return_value = mock_deps

            assert get_session_factory() is mock_factory

    def test_get_session_factory_not_initialized(self):
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            mock_deps = MagicMock()
            mock_deps.postgres_session_factory = None
            mock_get_deps.return_value = mock_deps

            with pytest.raises(RuntimeError, match="PostgreSQL session factory is not initialized"):
                get_session_factory()

    @pytest.mark.asyncio
    async def test_get_session_context_manager(self):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_factory = MagicMock(return_value=mock_session)

        with patch(
            "botspot.components.data.postgres_database.get_session_factory",
            return_value=mock_factory,
        ):
            async with get_session() as session:
                assert session is mock_session

        mock_factory.assert_called_once()


class TestBaseAndSetup:
    def test_base_and_metadata(self):
        assert Base is not None
        assert metadata is Base.metadata

    def test_setup_dispatcher_registers_dispose(self):
        dp = MagicMock()
        setup_dispatcher(dp)
        dp.shutdown.register.assert_called_once_with(dispose)


class TestBotManagerIntegration:
    def test_bot_manager_initializes_when_enabled(self):
        from botspot.core.bot_manager import BotManager

        Singleton._instances = {}
        mock_engine = MagicMock()
        mock_factory = MagicMock()

        with patch(
            "botspot.components.data.postgres_database.initialize",
            return_value=(mock_engine, mock_factory),
        ) as mock_init:
            with patch("botspot.core.bot_manager.BotspotSettings") as mock_settings_cls:
                mock_settings = MagicMock()
                mock_settings.mongo_database.enabled = False
                mock_settings.postgres_database.enabled = True
                mock_settings.postgres_database = PostgresDatabaseSettings(enabled=True)
                mock_settings.event_scheduler.enabled = False
                mock_settings.telethon_manager.enabled = False
                mock_settings.user_data.enabled = False
                mock_settings.single_user_mode.enabled = False
                mock_settings.access_control.enabled = False
                mock_settings.chat_binder.enabled = False
                mock_settings.llm_provider.enabled = False
                mock_settings.queue_manager.enabled = False
                mock_settings.message_aggregator.enabled = False
                mock_settings.chat_fetcher.enabled = False
                mock_settings.auto_archive.enabled = False
                mock_settings.s3_storage.enabled = False
                mock_settings_cls.return_value = mock_settings

                with patch("botspot.core.bot_manager.simple_user_cache.initialize"):
                    bm = BotManager()

        mock_init.assert_called_once()
        assert bm.deps._postgres_engine is mock_engine
        assert bm.deps._postgres_session_factory is mock_factory
