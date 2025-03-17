import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

# Mock the MongoDB client
pytest.importorskip("motor.motor_asyncio")
pytest.importorskip("pymongo")

# Mock MongoDB connection
@pytest.fixture(autouse=True)
def mock_mongo():
    with patch("motor.motor_asyncio.AsyncIOMotorClient") as mock_client:
        mock_db = MagicMock()
        mock_client.return_value.__getitem__.return_value = mock_db
        yield mock_client

from botspot.core.dependency_manager import DependencyManager
from botspot.core.botspot_settings import BotspotSettings


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    """Set up necessary environment variables for testing."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "mock_token_12345")
    monkeypatch.setenv("BOTSPOT_ERROR_HANDLER_EASTER_EGGS", "False")
    monkeypatch.setenv("BOTSPOT_ERROR_HANDLER_DEVELOPER_CHAT_ID", "123456789")
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("DATABASE_NAME", "test_db")
    monkeypatch.setenv("COLLECTION_NAME", "test_collection")
    monkeypatch.setenv("BOTSPOT_MONGO_DATABASE_CONN_STR", "mongodb://localhost:27017")
    monkeypatch.setenv("BOTSPOT_MONGO_DATABASE_DATABASE", "test_db")
    
    # Component settings overrides for tests
    monkeypatch.setenv("BOTSPOT_ERROR_HANDLER_ENABLED", "False")
    monkeypatch.setenv("BOTSPOT_BOT_INFO_ENABLED", "False")


@pytest.fixture
def settings():
    """Return BotspotSettings instance for testing."""
    return BotspotSettings()


@pytest.fixture
def dependency_manager(settings):
    """Create a dependency manager for testing."""
    return DependencyManager(settings=settings)


@pytest.fixture
def mock_bot():
    """Create a mock bot for testing."""
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    bot.send_photo = AsyncMock()
    bot.send_document = AsyncMock()
    return bot


@pytest.fixture
def mock_message():
    """Create a mock message for testing."""
    message = AsyncMock()
    message.answer = AsyncMock()
    message.reply = AsyncMock()
    message.chat = MagicMock()
    message.chat.id = 123456789
    message.from_user = MagicMock()
    message.from_user.id = 123456789
    message.from_user.is_bot = False
    message.from_user.username = "test_user"
    message.text = "Test message"
    return message


@pytest.fixture
def mock_callback_query():
    """Create a mock callback query for testing."""
    callback_query = AsyncMock()
    callback_query.message = MagicMock()
    callback_query.message.chat = MagicMock()
    callback_query.message.chat.id = 123456789
    callback_query.from_user = MagicMock()
    callback_query.from_user.id = 123456789
    callback_query.data = "test_data"
    callback_query.answer = AsyncMock()
    return callback_query


@pytest.fixture
def mock_botspot_deps():
    """Mock BotSpot dependencies for all tests"""
    with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_deps:
        mock_manager = MagicMock()
        mock_manager.bot = AsyncMock()
        mock_deps.return_value = mock_manager
        yield mock_deps


@pytest.fixture
def clean_singleton():
    """Reset the singleton instance before each test"""
    from botspot.utils.internal import Singleton
    # Clear the singleton instances before each test
    Singleton._instances = {}
    yield
    # Clean up after the test
    Singleton._instances = {}