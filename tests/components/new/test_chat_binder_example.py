"""Tests specifically for the chat_binder example application."""

import importlib
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import Message

# Add the necessary paths for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))


@pytest.fixture
def mock_message():
    """Create a mock message for testing command handlers."""
    message = AsyncMock(spec=Message)
    message.chat = AsyncMock()
    message.chat.id = 456
    message.from_user = AsyncMock()
    message.from_user.id = 123
    message.from_user.full_name = "Test User"
    message.text = "Test message"
    message.reply = AsyncMock()
    message.answer = AsyncMock()
    return message


@pytest.fixture
def chat_binder_demo_module():
    """Import the chat_binder_demo module."""
    return importlib.import_module("examples.components_examples.chat_binder_demo.bot")


class TestChatBinderDemoApp:
    def test_app_initialization(self, monkeypatch):
        """Test that the ChatBinderDemoApp can be instantiated."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "dummy_token")
        monkeypatch.setenv("BOTSPOT_CHAT_BINDER_ENABLED", "True")
        monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017")
        monkeypatch.setenv("DATABASE_NAME", "test_db")

        module = importlib.import_module("examples.components_examples.chat_binder_demo.bot")
        app_class = getattr(module, "ChatBinderDemoApp")

        # Instantiate the app
        app = app_class()

        # Check app properties
        assert app.name == "Chat Binder Demo"
        assert hasattr(app, "config")
        assert app.config is not None


class TestChatBinderCommands:
    @pytest.mark.asyncio
    async def test_start_handler(self, chat_binder_demo_module, mock_message):
        """Test that the start handler works correctly."""
        # Get the start handler from the module
        start_handler = chat_binder_demo_module.start_handler

        # Call the handler
        await start_handler(mock_message)

        # Verify the reply contains welcome text
        mock_message.reply.assert_called_once()
        reply_text = mock_message.reply.call_args[0][0]
        assert "Welcome to Chat Binder Demo" in reply_text
        assert "/bind_chat" in reply_text
        assert "/unbind_chat" in reply_text
        assert "/bind_status" in reply_text

    @pytest.mark.asyncio
    async def test_echo_to_bound_chats_no_bindings(self, chat_binder_demo_module, mock_message):
        """Test echo_to_bound_chats handler when no bindings exist."""
        # Get the echo_to_bound_chats handler
        echo_handler = chat_binder_demo_module.echo_to_bound_chats

        # Mock the get_user_bound_chats function
        with patch(
            "examples.components_examples.chat_binder_demo.bot.get_user_bound_chats"
        ) as mock_get_chats:
            # Set up the mock to return no bindings
            mock_get_chats.return_value = []

            # Call the handler
            await echo_handler(mock_message)

            # Verify get_user_bound_chats was called with correct args
            mock_get_chats.assert_called_once_with(123)

            # Verify no messages were sent
            mock_message.reply.assert_not_called()

    @pytest.mark.asyncio
    async def test_echo_to_bound_chats_with_bindings(self, chat_binder_demo_module, mock_message):
        """Test echo_to_bound_chats handler when bindings exist."""
        # Get the echo_to_bound_chats handler
        echo_handler = chat_binder_demo_module.echo_to_bound_chats

        # Create mock for bindings and send_safe
        with patch(
            "examples.components_examples.chat_binder_demo.bot.get_user_bound_chats"
        ) as mock_get_chats, patch(
            "examples.components_examples.chat_binder_demo.bot.send_safe"
        ) as mock_send_safe:

            # Set up the mock to return multiple bindings (including current chat and another chat)
            from botspot.components.new.chat_binder import BoundChatRecord

            mock_get_chats.return_value = [
                BoundChatRecord(user_id=123, chat_id=456, key="default"),  # Current chat
                BoundChatRecord(user_id=123, chat_id=789, key="work"),  # Another chat
            ]

            # Call the handler
            await echo_handler(mock_message)

            # Verify get_user_bound_chats was called with correct args
            mock_get_chats.assert_called_once_with(123)

            # Verify send_safe was called once for the other chat only
            mock_send_safe.assert_called_once()
            call_args = mock_send_safe.call_args[0]
            assert call_args[0] == 789  # The other chat ID
            assert "Echo from Test User" in call_args[1]
            assert "key: work" in call_args[1]
            assert "Test message" in call_args[1]

            # Verify the message about echoing was sent
            mock_message.reply.assert_called_once()
            assert "echoed to 1 bound chat" in mock_message.reply.call_args[0][0]


class TestRouterSetup:
    def test_router_command_registration(self, chat_binder_demo_module):
        """Test that the router has all the expected commands registered."""
        # Get the router from the module
        router = chat_binder_demo_module.router

        # Check that handlers are registered
        assert len(router.message.handlers) > 0

        # Extract handler functions from the router
        handler_functions = []
        for handler in router.message.handlers:
            if hasattr(handler, "callback"):
                handler_functions.append(handler.callback.__name__)

        # Verify that our key handlers are registered
        assert "start_handler" in handler_functions
        assert "echo_to_bound_chats" in handler_functions
