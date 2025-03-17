import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from botspot.core.dependency_manager import DependencyManager
from botspot.core.botspot_settings import BotspotSettings


@pytest.fixture(autouse=True)
def setup_env():
    """Set up necessary environment variables for testing."""
    os.environ["TELEGRAM_BOT_TOKEN"] = "mock_token_12345"
    os.environ["BOTSPOT_ERROR_HANDLER_EASTER_EGGS"] = "False"
    os.environ["BOTSPOT_ERROR_HANDLER_DEVELOPER_CHAT_ID"] = "123456789"
    
    # Cleanup after test
    yield
    if "TELEGRAM_BOT_TOKEN" in os.environ:
        del os.environ["TELEGRAM_BOT_TOKEN"]
    if "BOTSPOT_ERROR_HANDLER_EASTER_EGGS" in os.environ:
        del os.environ["BOTSPOT_ERROR_HANDLER_EASTER_EGGS"]
    if "BOTSPOT_ERROR_HANDLER_DEVELOPER_CHAT_ID" in os.environ:
        del os.environ["BOTSPOT_ERROR_HANDLER_DEVELOPER_CHAT_ID"]


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