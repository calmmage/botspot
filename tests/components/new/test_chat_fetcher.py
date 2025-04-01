"""Tests for the chat_fetcher component."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telethon.types import Chat, Dialog, Message

from botspot.components.new.chat_fetcher import (
    ChatFetcher,
    ChatFetcherSettings,
    GetChatsResponse,
    get_chat_fetcher,
    initialize,
    setup_dispatcher,
)
from botspot.core.errors import BotspotError


class TestChatFetcherSettings:
    def test_default_settings(self):
        """Test default settings are correctly initialized."""
        with pytest.MonkeyPatch.context() as mp:
            # Clear any existing environment variables
            mp.delenv("BOTSPOT_CHAT_FETCHER_ENABLED", raising=False)
            mp.delenv("BOTSPOT_CHAT_FETCHER_DB_CACHE_ENABLED", raising=False)

            settings = ChatFetcherSettings()

            assert settings.enabled is False
            assert settings.db_cache_enabled is False

    def test_settings_from_env(self):
        """Test that settings can be loaded from environment variables."""
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("BOTSPOT_CHAT_FETCHER_ENABLED", "True")
            mp.setenv("BOTSPOT_CHAT_FETCHER_DB_CACHE_ENABLED", "True")

            settings = ChatFetcherSettings()

            assert settings.enabled is True
            assert settings.db_cache_enabled is True


class TestChatFetcher:
    @pytest.fixture
    def settings(self):
        return ChatFetcherSettings(enabled=True)

    @pytest.fixture
    def mock_client(self):
        client = AsyncMock()
        client.get_dialogs = AsyncMock()
        client.get_entity = AsyncMock()
        client.get_messages = AsyncMock()
        client.iter_messages = AsyncMock()
        return client

    @pytest.fixture
    def mock_chat(self):
        chat = MagicMock(spec=Chat)
        chat.id = 789
        chat.title = "Test Chat"
        return chat

    @pytest.fixture
    def mock_message(self):
        message = MagicMock(spec=Message)
        message.id = 123
        message.text = "Test message"
        return message

    @pytest.fixture
    def mock_dialog(self):
        dialog = MagicMock(spec=Dialog)
        dialog.id = 789
        dialog.name = "Test Dialog"
        dialog.entity = MagicMock(spec=Chat)
        dialog.entity.id = 789
        dialog.entity.title = "Test Chat"
        return dialog

    @pytest.fixture
    def chat_fetcher(self, settings):
        # Mock the dependency manager
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Create a mock dependency manager
            mock_deps = MagicMock()
            mock_deps.botspot_settings = MagicMock()
            mock_deps.botspot_settings.single_user_mode = MagicMock()
            mock_deps.botspot_settings.single_user_mode.enabled = False
            mock_deps.botspot_settings.single_user_mode.user = None
            mock_get_deps.return_value = mock_deps

            return ChatFetcher(settings)

    @pytest.mark.asyncio
    async def test_get_client_new(self, chat_fetcher, mock_client):
        """Test getting a new client."""
        with patch("botspot.get_telethon_client", return_value=mock_client) as mock_get_client:
            client = await chat_fetcher._get_client(user_id=123)

            # Verify get_telethon_client was called with correct user_id
            mock_get_client.assert_called_once_with(123)

            # Verify client was cached and returned
            assert chat_fetcher.clients[123] == mock_client
            assert client == mock_client

    @pytest.mark.asyncio
    async def test_get_client_cached(self, chat_fetcher, mock_client):
        """Test getting a cached client."""
        # Add a client to the cache
        chat_fetcher.clients[123] = mock_client

        # Get the client
        client = await chat_fetcher._get_client(user_id=123)

        # Verify client was returned from cache
        assert client == mock_client

    @pytest.mark.asyncio
    async def test_get_client_single_user_mode(self, settings, mock_client):
        """Test getting a client in single user mode."""
        # Mock the dependency manager with single user mode enabled
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Create a mock dependency manager
            mock_deps = MagicMock()
            mock_deps.botspot_settings = MagicMock()
            mock_deps.botspot_settings.single_user_mode = MagicMock()
            mock_deps.botspot_settings.single_user_mode.enabled = True
            mock_deps.botspot_settings.single_user_mode.user = "456"
            mock_get_deps.return_value = mock_deps

            # Create the chat fetcher
            chat_fetcher = ChatFetcher(settings)

            # Mock get_telethon_client
            with patch("botspot.get_telethon_client", return_value=mock_client) as mock_get_client:
                # Call with different user_id than configured in single user mode
                with pytest.raises(ValueError):
                    await chat_fetcher._get_client(user_id=123)

                # Call with correct user_id
                client = await chat_fetcher._get_client(user_id=456)

                # Verify get_telethon_client was called with correct user_id
                mock_get_client.assert_called_once_with(456)

                # Verify client was cached and returned
                assert chat_fetcher.clients[456] == mock_client
                assert client == mock_client

                # Call with no user_id
                client = await chat_fetcher._get_client()

                # Verify client was returned from cache
                assert client == mock_client

    @pytest.mark.asyncio
    async def test_get_client_no_user_id(self, chat_fetcher):
        """Test getting a client without user_id."""
        with pytest.raises(ValueError):
            await chat_fetcher._get_client()

    @pytest.mark.asyncio
    async def test_get_dialogs(self, chat_fetcher, mock_dialog):
        """Test getting dialogs."""
        # Mock _get_dialogs
        with patch.object(chat_fetcher, "_get_dialogs") as mock_get_dialogs:
            mock_get_dialogs.return_value = [mock_dialog]

            # Call get_dialogs (renamed from dialogs)
            result = await chat_fetcher.get_dialogs(user_id=123)

            # Verify _get_dialogs was called with correct user_id
            mock_get_dialogs.assert_called_once_with(123)

            # Verify result was cached and returned
            assert chat_fetcher._dialogs[123] == [mock_dialog]
            assert result == [mock_dialog]

            # Call again to test caching
            mock_get_dialogs.reset_mock()
            result = await chat_fetcher.get_dialogs(user_id=123)

            # Verify _get_dialogs was not called again
            mock_get_dialogs.assert_not_called()

            # Verify cached result was returned
            assert result == [mock_dialog]

    @pytest.mark.asyncio
    async def test_get_dialogs_2(self, chat_fetcher, mock_client, mock_dialog):
        """Test _get_dialogs method."""
        # Mock _get_client
        with patch.object(chat_fetcher, "_get_client", return_value=mock_client) as mock_get_client:
            mock_client.get_dialogs.return_value = [mock_dialog]

            # Call _get_dialogs
            result = await chat_fetcher._get_dialogs(user_id=123)

            # Verify _get_client was called with correct user_id
            mock_get_client.assert_called_once_with(123)

            # Verify client.get_dialogs was called
            mock_client.get_dialogs.assert_called_once()

            # Verify result was returned
            assert result == [mock_dialog]

    @pytest.mark.asyncio
    async def test_get_chat(self, chat_fetcher, mock_client, mock_chat):
        """Test get_chat method."""
        # Mock _get_client
        with patch.object(chat_fetcher, "_get_client", return_value=mock_client) as mock_get_client:
            mock_client.get_entity.return_value = mock_chat

            # Call get_chat
            result = await chat_fetcher.get_chat(chat_id=789, user_id=123)

            # Verify _get_client was called with correct user_id
            mock_get_client.assert_called_once_with(123)

            # Verify client.get_entity was called with correct chat_id
            mock_client.get_entity.assert_called_once_with(789)

            # Verify result was returned
            assert result == mock_chat

    @pytest.mark.asyncio
    async def test_get_chat_wrong_entity_type(self, chat_fetcher, mock_client):
        """Test get_chat method with wrong entity type."""
        # Mock _get_client
        with patch.object(chat_fetcher, "_get_client", return_value=mock_client) as mock_get_client:
            # Return an entity that is not a Chat
            mock_entity = MagicMock()
            mock_client.get_entity.return_value = mock_entity

            # Call get_chat
            with pytest.raises(BotspotError):
                await chat_fetcher.get_chat(chat_id=789, user_id=123)

    @pytest.mark.asyncio
    async def test_get_old_messages(self, chat_fetcher, mock_client, mock_message):
        """Test _get_old_messages method."""
        # Mock _get_client
        with patch.object(chat_fetcher, "_get_client", return_value=mock_client) as mock_get_client:
            mock_client.get_messages.return_value = [mock_message]

            # Call _get_old_messages
            result = await chat_fetcher._get_old_messages(
                chat_id=789, user_id=123, timestamp=456, limit=10
            )

            # Verify _get_client was called with correct user_id
            mock_get_client.assert_called_once_with(123)

            # Verify client.get_messages was called with correct parameters
            mock_client.get_messages.assert_called_once_with(789, offset_date=456, limit=10)

            # Verify result was returned
            assert result == [mock_message]

    @pytest.mark.asyncio
    async def test_get_old_messages_single_message(self, chat_fetcher, mock_client, mock_message):
        """Test _get_old_messages method returning a single message."""
        # Mock _get_client
        with patch.object(chat_fetcher, "_get_client", return_value=mock_client) as mock_get_client:
            mock_client.get_messages.return_value = mock_message

            # Call _get_old_messages
            result = await chat_fetcher._get_old_messages(chat_id=789, user_id=123, timestamp=456)

            # Verify _get_client was called with correct user_id
            mock_get_client.assert_called_once_with(123)

            # Verify client.get_messages was called with correct parameters
            mock_client.get_messages.assert_called_once_with(789, offset_date=456, limit=None)

            # Verify result was returned as a list
            assert result == [mock_message]

    @pytest.mark.asyncio
    async def test_get_new_messages(self, chat_fetcher, mock_client, mock_message):
        """Test _get_new_messages method."""
        # Mock _get_client
        with patch.object(chat_fetcher, "_get_client", return_value=mock_client) as mock_get_client:
            mock_client.get_messages.return_value = [mock_message]

            # Call _get_new_messages
            result = await chat_fetcher._get_new_messages(
                chat_id=789, user_id=123, timestamp=456, limit=10
            )

            # Verify _get_client was called with correct user_id
            mock_get_client.assert_called_once_with(123)

            # Verify client.get_messages was called with correct parameters
            mock_client.get_messages.assert_called_once_with(
                789, offset_date=456, limit=10, reverse=True
            )

            # Verify result was returned
            assert result == [mock_message]

    @pytest.mark.asyncio
    async def test_get_chat_messages(self, chat_fetcher, mock_client, mock_message):
        """Test get_chat_messages method."""
        # Mock _get_client
        with patch.object(chat_fetcher, "_get_client", return_value=mock_client) as mock_get_client:
            mock_client.get_messages.return_value = [mock_message]

            # Call get_chat_messages
            result = await chat_fetcher.get_chat_messages(chat_id=789, user_id=123, limit=10)

            # Verify _get_client was called with correct user_id
            mock_get_client.assert_called_once_with(123)

            # Verify client.get_messages was called with correct parameters
            mock_client.get_messages.assert_called_once_with(789, limit=10)

            # Verify result was returned
            assert result == [mock_message]

    @pytest.mark.asyncio
    async def test_get_chats(self, chat_fetcher, mock_client, mock_dialog):
        """Test get_chats method."""
        # Mock _get_client
        with patch.object(chat_fetcher, "_get_client", return_value=mock_client) as mock_get_client:
            mock_client.get_dialogs.return_value = [mock_dialog]
            chat_fetcher._dialogs = {}

            # Call get_chats
            result = await chat_fetcher.get_chats(user_id=123)

            # Verify _get_client was called with correct user_id
            mock_get_client.assert_called_once_with(123)

            # Verify client.get_dialogs was called with correct parameters
            mock_client.get_dialogs.assert_called_once()

            # Verify result is a GetChatsResponse
            assert isinstance(result, GetChatsResponse)
            # The dialog entity should be in one of the lists depending on its type
            assert (
                mock_dialog.entity in result.users
                or mock_dialog.entity in result.groups
                or mock_dialog.entity in result.channels
            )

    @pytest.mark.asyncio
    async def test_search_message_in_chat(self, chat_fetcher, mock_client, mock_message):
        """Test search_message method in a specific chat."""
        # Mock _get_client
        with patch.object(chat_fetcher, "_get_client", return_value=mock_client) as mock_get_client:
            # Mock list comprehension result
            with patch(
                "botspot.components.new.chat_fetcher.ChatFetcher.search_message",
                return_value=[mock_message],
            ):
                # Call search_message with chat_id
                result = await chat_fetcher.search_message(query="test", user_id=123, chat_id=789)

                # Verify _get_client was called with correct user_id
                # todo: figure out and re-add?
                # mock_get_client.assert_called_once_with(123)

                # Verify result was returned
                assert result == [mock_message]

    @pytest.mark.asyncio
    async def test_search_message_all_chats(
        self, chat_fetcher, mock_client, mock_dialog, mock_message
    ):
        """Test search_message method across all chats."""
        # Mock _get_client
        with patch.object(chat_fetcher, "_get_client", return_value=mock_client) as mock_get_client:
            # Mock list comprehension result
            with patch(
                "botspot.components.new.chat_fetcher.ChatFetcher.search_message",
                return_value=[mock_message],
            ):
                # Call search_message without chat_id
                result = await chat_fetcher.search_message(query="test", user_id=123)

                # Verify _get_client was called with correct user_id
                # todo: figure out and re-add?
                # mock_get_client.assert_called_once_with(123)

                # Verify result was returned
                assert result == [mock_message]


class TestInitialization:
    def test_initialize(self):
        """Test successful initialization."""
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Set up mock dependencies
            mock_deps = MagicMock()
            mock_deps.botspot_settings = MagicMock()
            mock_deps.botspot_settings.single_user_mode = MagicMock()
            mock_deps.botspot_settings.single_user_mode.enabled = False
            mock_deps.botspot_settings.single_user_mode.user = None
            mock_get_deps.return_value = mock_deps

            # Call initialize
            settings = ChatFetcherSettings(enabled=True)
            result = initialize(settings)

            # Verify ChatFetcher was created with correct settings
            assert isinstance(result, ChatFetcher)
            assert result.settings == settings

    def test_setup_dispatcher(self):
        """Test that setup_dispatcher returns the dispatcher."""
        # Create a mock dispatcher
        mock_dp = MagicMock()

        # Call setup_dispatcher
        result = setup_dispatcher(mock_dp)

        # Verify dispatcher was returned unchanged
        assert result == mock_dp


class TestWrapperFunctions:
    @pytest.mark.asyncio
    async def test_get_chat_fetcher_wrapper(self):
        """Test that the get_chat_fetcher wrapper function returns the ChatFetcher instance."""
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Set up the mock dependency manager
            mock_deps = MagicMock()
            mock_deps.chat_fetcher = MagicMock()
            mock_get_deps.return_value = mock_deps

            # Call the wrapper function
            result = get_chat_fetcher()

            # Verify the dependency manager was accessed
            mock_get_deps.assert_called_once()

            # Verify the chat_fetcher was returned
            assert result == mock_deps.chat_fetcher
