from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import the functions to test
from botspot.utils.deps_getters import (
    get_bot,
    get_database,
    get_dispatcher,
    get_mongo_client,
    get_scheduler,
    get_telethon_client,
    get_telethon_manager,
    get_user_manager,
)


class TestGetBot:
    def test_get_bot_success(self):
        """Test successful retrieval of bot"""
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Setup
            mock_deps = MagicMock()
            mock_bot = MagicMock()
            mock_deps.bot = mock_bot
            mock_get_deps.return_value = mock_deps

            # Execute
            result = get_bot()

            # Verify
            assert result is mock_bot
            mock_get_deps.assert_called_once()

    def test_get_bot_not_initialized(self):
        """Test error when bot is not initialized"""
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Setup
            mock_deps = MagicMock()
            mock_deps.bot = None
            mock_get_deps.return_value = mock_deps

            # Execute & Verify
            with pytest.raises(AssertionError, match="Bot is not initialized"):
                get_bot()

            mock_get_deps.assert_called_once()


class TestGetDispatcher:
    def test_get_dispatcher_success(self):
        """Test successful retrieval of dispatcher"""
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Setup
            mock_deps = MagicMock()
            mock_dispatcher = MagicMock()
            mock_deps.dispatcher = mock_dispatcher
            mock_get_deps.return_value = mock_deps

            # Execute
            result = get_dispatcher()

            # Verify
            assert result is mock_dispatcher
            mock_get_deps.assert_called_once()

    def test_get_dispatcher_not_initialized(self):
        """Test error when dispatcher is not initialized"""
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Setup
            mock_deps = MagicMock()
            mock_deps.dispatcher = None
            mock_get_deps.return_value = mock_deps

            # Execute & Verify
            with pytest.raises(AssertionError, match="Dispatcher is not initialized"):
                get_dispatcher()

            mock_get_deps.assert_called_once()


class TestGetScheduler:
    def test_get_scheduler_success(self):
        """Test successful retrieval of scheduler"""
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Setup
            mock_deps = MagicMock()
            mock_scheduler = MagicMock()
            mock_deps.scheduler = mock_scheduler
            mock_get_deps.return_value = mock_deps

            # Execute
            result = get_scheduler()

            # Verify
            assert result is mock_scheduler
            mock_get_deps.assert_called_once()

    def test_get_scheduler_not_initialized(self):
        """Test error when scheduler is not initialized"""
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Setup
            mock_deps = MagicMock()
            mock_deps.scheduler = None
            mock_get_deps.return_value = mock_deps

            # Execute & Verify
            with pytest.raises(AssertionError, match="Scheduler is not initialized"):
                get_scheduler()

            mock_get_deps.assert_called_once()


class TestGetTelethonManager:
    def test_get_telethon_manager_success(self):
        """Test successful retrieval of telethon manager"""
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Setup
            mock_deps = MagicMock()
            mock_telethon_manager = MagicMock()
            mock_deps.telethon_manager = mock_telethon_manager
            mock_get_deps.return_value = mock_deps

            # Execute
            result = get_telethon_manager()

            # Verify
            assert result is mock_telethon_manager
            mock_get_deps.assert_called_once()

    def test_get_telethon_manager_not_initialized(self):
        """Test error when telethon manager is not initialized"""
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Setup
            mock_deps = MagicMock()
            mock_deps.telethon_manager = None
            mock_get_deps.return_value = mock_deps

            # Execute & Verify
            with pytest.raises(RuntimeError, match="TelethonManager is not initialized"):
                get_telethon_manager()

            mock_get_deps.assert_called_once()


class TestGetTelethonClient:
    @pytest.mark.asyncio
    async def test_get_telethon_client_success(self):
        """Test successful retrieval of telethon client"""
        with patch("botspot.utils.deps_getters.get_telethon_manager") as mock_get_telethon_manager:
            # Setup
            mock_manager = MagicMock()
            mock_client = MagicMock()
            mock_manager.get_client = AsyncMock(return_value=mock_client)
            mock_get_telethon_manager.return_value = mock_manager

            # Execute
            result = await get_telethon_client(123456789)

            # Verify
            assert result is mock_client
            mock_get_telethon_manager.assert_called_once()
            mock_manager.get_client.assert_called_once_with(123456789, None)

    @pytest.mark.asyncio
    async def test_get_telethon_client_with_state(self):
        """Test retrieval of telethon client with state"""
        with patch("botspot.utils.deps_getters.get_telethon_manager") as mock_get_telethon_manager:
            # Setup
            mock_manager = MagicMock()
            mock_client = MagicMock()
            mock_state = MagicMock()
            mock_manager.get_client = AsyncMock(return_value=mock_client)
            mock_get_telethon_manager.return_value = mock_manager

            # Execute
            result = await get_telethon_client(123456789, mock_state)

            # Verify
            assert result is mock_client
            mock_get_telethon_manager.assert_called_once()
            mock_manager.get_client.assert_called_once_with(123456789, mock_state)

    @pytest.mark.asyncio
    async def test_get_telethon_client_not_found(self):
        """Test error when telethon client is not found"""
        with patch("botspot.utils.deps_getters.get_telethon_manager") as mock_get_telethon_manager:
            # Setup
            mock_manager = MagicMock()
            mock_manager.get_client = AsyncMock(return_value=None)
            mock_get_telethon_manager.return_value = mock_manager

            # Execute & Verify
            with pytest.raises(RuntimeError, match="No active Telethon client found for user"):
                await get_telethon_client(123456789)

            mock_get_telethon_manager.assert_called_once()
            mock_manager.get_client.assert_called_once_with(123456789, None)


class TestGetMongoClient:
    def test_get_mongo_client_success(self):
        """Test successful retrieval of MongoDB client"""
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Setup
            mock_deps = MagicMock()
            mock_client = MagicMock()
            mock_deps.mongo_client = mock_client
            mock_get_deps.return_value = mock_deps

            # Execute
            result = get_mongo_client()

            # Verify
            assert result is mock_client
            mock_get_deps.assert_called_once()

    def test_get_mongo_client_not_initialized(self):
        """Test error when MongoDB client is not initialized"""
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Setup
            mock_deps = MagicMock()
            mock_deps.mongo_client = None
            mock_get_deps.return_value = mock_deps

            # Execute & Verify
            with pytest.raises(RuntimeError, match="MongoDB client is not initialized"):
                get_mongo_client()

            mock_get_deps.assert_called_once()


class TestGetDatabase:
    def test_get_database_success(self):
        """Test successful retrieval of database"""
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Setup
            mock_deps = MagicMock()
            mock_db = MagicMock()
            mock_deps.mongo_database = mock_db
            mock_get_deps.return_value = mock_deps

            # Execute
            result = get_database()

            # Verify
            assert result is mock_db
            mock_get_deps.assert_called_once()

    def test_get_database_not_initialized(self):
        """Test error when database is not initialized"""
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Setup
            mock_deps = MagicMock()
            mock_deps.mongo_database = None
            mock_get_deps.return_value = mock_deps

            # Execute & Verify
            with pytest.raises(RuntimeError, match="MongoDB database is not initialized"):
                get_database()

            mock_get_deps.assert_called_once()


class TestGetUserManager:
    def test_get_user_manager_success(self):
        """Test successful retrieval of user manager"""
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Setup
            mock_deps = MagicMock()
            mock_user_manager = MagicMock()
            mock_deps.user_manager = mock_user_manager
            mock_get_deps.return_value = mock_deps

            # Execute
            result = get_user_manager()

            # Verify
            assert result is mock_user_manager
            mock_get_deps.assert_called_once()

    def test_get_user_manager_not_initialized(self):
        """Test error when user manager is not initialized"""
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Setup
            mock_deps = MagicMock()
            mock_deps.user_manager = None
            mock_get_deps.return_value = mock_deps

            # Execute & Verify
            with pytest.raises(RuntimeError, match="UserManager is not initialized"):
                get_user_manager()

            mock_get_deps.assert_called_once()
