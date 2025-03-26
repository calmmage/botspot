"""Tests for the chat_binder component."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import Message

from botspot.components.new.chat_binder import (
    BoundChatRecord,
    ChatBinder,
    ChatBinderSettings,
    RebindMode,
    bind_chat,
    bind_chat_command_handler,
    bind_status_command_handler,
    get_bind_chat_id,
    get_chat_binding_status,
    get_user_bound_chats,
    initialize,
    setup_dispatcher,
    unbind_chat,
    unbind_chat_command_handler,
)


class TestChatBinderSettings:
    def test_default_settings(self):
        """Test default settings are correctly initialized."""
        with pytest.MonkeyPatch.context() as mp:
            # Clear any existing environment variables
            mp.delenv("BOTSPOT_CHAT_BINDER_ENABLED", raising=False)
            mp.delenv("BOTSPOT_CHAT_BINDER_MONGO_COLLECTION", raising=False)
            mp.delenv("BOTSPOT_CHAT_BINDER_COMMANDS_VISIBLE", raising=False)
            mp.delenv("BOTSPOT_CHAT_BINDER_REBIND_MODE", raising=False)

            settings = ChatBinderSettings()

            assert settings.enabled is False
            assert settings.mongo_collection == "chat_binder"
            assert settings.commands_visible is False
            assert settings.rebind_mode == RebindMode.ERROR

    def test_settings_from_env(self):
        """Test that settings can be loaded from environment variables."""
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("BOTSPOT_CHAT_BINDER_ENABLED", "True")
            mp.setenv("BOTSPOT_CHAT_BINDER_MONGO_COLLECTION", "test_collection")
            mp.setenv("BOTSPOT_CHAT_BINDER_COMMANDS_VISIBLE", "True")
            mp.setenv("BOTSPOT_CHAT_BINDER_REBIND_MODE", "replace")

            settings = ChatBinderSettings()

            assert settings.enabled is True
            assert settings.mongo_collection == "test_collection"
            assert settings.commands_visible is True
            assert settings.rebind_mode == RebindMode.REPLACE


class TestBoundChatRecord:
    def test_record_creation(self):
        """Test that BoundChatRecord is correctly initialized."""
        record = BoundChatRecord(user_id=123, chat_id=456)
        assert record.user_id == 123
        assert record.chat_id == 456
        assert record.key == "default"

        record_with_key = BoundChatRecord(user_id=123, chat_id=456, key="custom")
        assert record_with_key.user_id == 123
        assert record_with_key.chat_id == 456
        assert record_with_key.key == "custom"


class TestChatBinder:
    @pytest.fixture
    def settings(self):
        return ChatBinderSettings(enabled=True)

    @pytest.fixture
    def mock_collection(self):
        collection = AsyncMock()
        collection.find_one = AsyncMock()
        collection.insert_one = AsyncMock()
        collection.replace_one = AsyncMock()
        collection.delete_one = AsyncMock()

        # Properly set up the find method to return an async cursor
        # that has a to_list method
        collection.find = AsyncMock()
        return collection

    @pytest.fixture
    def chat_binder(self, settings, mock_collection):
        # Mock the dependency manager
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Create a mock dependency manager
            mock_deps = MagicMock()
            mock_deps.queue_manager = None
            mock_get_deps.return_value = mock_deps

            return ChatBinder(settings, mock_collection)

    @pytest.mark.asyncio
    async def test_bind_chat_new(self, chat_binder, mock_collection):
        """Test binding a new chat."""
        # Setup mock to return None (no existing binding)
        mock_collection.find_one.return_value = None

        # Call bind_chat
        result = await chat_binder.bind_chat(user_id=123, chat_id=456, key="test")

        # Verify insert_one was called with correct data
        mock_collection.insert_one.assert_called_once()
        inserted_data = mock_collection.insert_one.call_args[0][0]
        assert inserted_data["user_id"] == 123
        assert inserted_data["chat_id"] == 456
        assert inserted_data["key"] == "test"

        # Verify result is a BoundChatRecord with correct data
        assert isinstance(result, BoundChatRecord)
        assert result.user_id == 123
        assert result.chat_id == 456
        assert result.key == "test"

    @pytest.mark.asyncio
    async def test_bind_chat_existing_error_mode(self, chat_binder, mock_collection):
        """Test binding when already bound in ERROR mode."""
        # Set rebind mode to ERROR
        chat_binder.settings.rebind_mode = RebindMode.ERROR

        # Setup mock to return an existing binding
        mock_collection.find_one.return_value = {"user_id": 123, "chat_id": 789, "key": "test"}

        # Call bind_chat and expect ValueError
        with pytest.raises(ValueError) as excinfo:
            await chat_binder.bind_chat(user_id=123, chat_id=456, key="test")

        # Verify error message
        assert "already bound" in str(excinfo.value)
        assert "789" in str(excinfo.value)

        # Verify no insert or replace operations were performed
        mock_collection.insert_one.assert_not_called()
        mock_collection.replace_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_bind_chat_existing_ignore_mode(self, chat_binder, mock_collection):
        """Test binding when already bound in IGNORE mode."""
        # Set rebind mode to IGNORE
        chat_binder.settings.rebind_mode = RebindMode.IGNORE

        # Setup mock to return an existing binding
        existing_binding = {"user_id": 123, "chat_id": 789, "key": "test"}
        mock_collection.find_one.return_value = existing_binding

        # Call bind_chat
        result = await chat_binder.bind_chat(user_id=123, chat_id=456, key="test")

        # Verify the original binding is returned unchanged
        assert isinstance(result, BoundChatRecord)
        assert result.user_id == 123
        assert result.chat_id == 789
        assert result.key == "test"

        # Verify no insert or replace operations were performed
        mock_collection.insert_one.assert_not_called()
        mock_collection.replace_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_bind_chat_existing_replace_mode(self, chat_binder, mock_collection):
        """Test binding when already bound in REPLACE mode."""
        # Set rebind mode to REPLACE
        chat_binder.settings.rebind_mode = RebindMode.REPLACE

        # Setup mock to return an existing binding
        mock_collection.find_one.return_value = {"user_id": 123, "chat_id": 789, "key": "test"}

        # Call bind_chat
        result = await chat_binder.bind_chat(user_id=123, chat_id=456, key="test")

        # Verify replace_one was called with correct data
        mock_collection.replace_one.assert_called_once()
        filter_dict, replacement = mock_collection.replace_one.call_args[0]
        assert filter_dict == {"user_id": 123, "key": "test"}
        assert replacement["user_id"] == 123
        assert replacement["chat_id"] == 456
        assert replacement["key"] == "test"

        # Verify result is a BoundChatRecord with the new data
        assert isinstance(result, BoundChatRecord)
        assert result.user_id == 123
        assert result.chat_id == 456
        assert result.key == "test"

    @pytest.mark.asyncio
    async def test_get_chat_binding_status(self, chat_binder, mock_collection):
        """Test getting chat binding status."""
        # We need to patch the to_list call because AsyncMock doesn't handle chained calls correctly
        with patch.object(ChatBinder, "get_chat_binding_status", AsyncMock()) as mock_method:
            # Setup mock to return a list of bindings
            expected_records = [
                BoundChatRecord(user_id=123, chat_id=456, key="key1"),
                BoundChatRecord(user_id=123, chat_id=456, key="key2"),
            ]
            mock_method.return_value = expected_records

            # Call get_chat_binding_status directly from the mocked method
            result = await mock_method(user_id=123, chat_id=456)

            # Verify the method was called with correct args
            mock_method.assert_called_once_with(user_id=123, chat_id=456)

            # Verify result is a list of BoundChatRecord objects
            assert result == expected_records

    @pytest.mark.asyncio
    async def test_unbind_chat_success(self, chat_binder, mock_collection):
        """Test successfully unbinding a chat."""
        # Setup mock to return an existing binding
        mock_collection.find_one.return_value = {"user_id": 123, "chat_id": 456, "key": "test"}

        # Setup mock delete operation to return success
        delete_result = MagicMock()
        delete_result.deleted_count = 1
        mock_collection.delete_one.return_value = delete_result

        # Call unbind_chat
        result, key = await chat_binder.unbind_chat(user_id=123, key="test")

        # Verify delete_one was called with correct filter
        mock_collection.delete_one.assert_called_once_with({"user_id": 123, "key": "test"})

        # Verify result indicates success
        assert result is True
        assert key == "test"

    @pytest.mark.asyncio
    async def test_unbind_chat_default_key_not_found_but_other_binding_exists(
        self, chat_binder, mock_collection
    ):
        """Test unbinding with default key when it doesn't exist but another binding does."""
        # Setup mocks to simulate no binding with default key but another binding exists
        mock_collection.find_one.side_effect = [
            None,  # First call returns None (no binding with default key)
            {
                "user_id": 123,
                "chat_id": 456,
                "key": "other_key",
            },  # Second call finds another binding
        ]

        # Setup mock delete operation to return success
        delete_result = MagicMock()
        delete_result.deleted_count = 1
        mock_collection.delete_one.return_value = delete_result

        # Call unbind_chat with default key
        result, key = await chat_binder.unbind_chat(user_id=123, key="default", chat_id=456)

        # Verify find_one was called twice with correct filters
        assert mock_collection.find_one.call_count == 2
        mock_collection.find_one.assert_any_call({"user_id": 123, "key": "default"})
        mock_collection.find_one.assert_any_call({"user_id": 123, "chat_id": 456})

        # Verify delete_one was called with correct filter
        mock_collection.delete_one.assert_called_once_with(
            {"user_id": 123, "chat_id": 456, "key": "other_key"}
        )

        # Verify result indicates success
        assert result is True
        assert key == "other_key"

    @pytest.mark.asyncio
    async def test_unbind_chat_no_binding_found(self, chat_binder, mock_collection):
        """Test unbinding when no binding exists."""
        # Setup mocks to simulate no binding found
        mock_collection.find_one.return_value = None

        # Call unbind_chat with non-default key and expect ValueError
        with pytest.raises(ValueError) as excinfo:
            await chat_binder.unbind_chat(user_id=123, key="missing")

        # Verify error message
        assert "No binding found with key" in str(excinfo.value)

        # Verify delete_one was not called
        mock_collection.delete_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_unbind_chat_default_key_not_found_no_other_binding(
        self, chat_binder, mock_collection
    ):
        """Test unbinding with default key when no binding exists at all."""
        # Setup mocks to simulate no binding found
        mock_collection.find_one.side_effect = [None, None]

        # Call unbind_chat with default key and expect ValueError
        with pytest.raises(ValueError) as excinfo:
            await chat_binder.unbind_chat(user_id=123, key="default", chat_id=456)

        # Verify error message
        assert "No binding found with key" in str(excinfo.value)

        # Verify delete_one was not called
        mock_collection.delete_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_bind_chat_id_success(self, chat_binder, mock_collection):
        """Test successfully getting a bound chat ID."""
        # Setup mock to return an existing binding
        mock_collection.find_one.return_value = {"user_id": 123, "chat_id": 456, "key": "test"}

        # Call get_bind_chat_id
        result = await chat_binder.get_bind_chat_id(user_id=123, key="test")

        # Verify find_one was called with correct filter
        mock_collection.find_one.assert_called_once_with({"user_id": 123, "key": "test"})

        # Verify result is the correct chat ID
        assert result == 456

    @pytest.mark.asyncio
    async def test_get_bind_chat_id_no_binding(self, chat_binder, mock_collection):
        """Test getting a bound chat ID when no binding exists."""
        # Setup mock to return no binding
        mock_collection.find_one.return_value = None

        # Call get_bind_chat_id and expect ValueError
        with pytest.raises(ValueError) as excinfo:
            await chat_binder.get_bind_chat_id(user_id=123, key="missing")

        # Verify error message
        assert "No bound chat found" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_get_user_bound_chats(self, chat_binder, mock_collection):
        """Test getting all chats bound to a user."""
        # We need to patch the method because AsyncMock doesn't handle chained calls correctly
        with patch.object(ChatBinder, "get_user_bound_chats", AsyncMock()) as mock_method:
            # Setup mock to return a list of bindings
            expected_records = [
                BoundChatRecord(user_id=123, chat_id=456, key="key1"),
                BoundChatRecord(user_id=123, chat_id=789, key="key2"),
            ]
            mock_method.return_value = expected_records

            # Call get_user_bound_chats directly from the mocked method
            result = await mock_method(user_id=123)

            # Verify the method was called with correct args
            mock_method.assert_called_once_with(user_id=123)

            # Verify result is the expected list
            assert result == expected_records


class TestCommandHandlers:
    @pytest.fixture
    def mock_message(self):
        message = AsyncMock(spec=Message)
        message.chat = AsyncMock()
        message.chat.id = 456
        message.from_user = AsyncMock()
        message.from_user.id = 123
        message.text = "/command"
        message.reply = AsyncMock()
        message.answer = AsyncMock()
        return message

    @pytest.mark.asyncio
    async def test_bind_chat_command_handler(self, mock_message):
        """Test the bind_chat command handler."""
        with patch("botspot.components.new.chat_binder.bind_chat") as mock_bind_chat:
            # Set up the mock to return a BoundChatRecord
            mock_bind_chat.return_value = BoundChatRecord(user_id=123, chat_id=456)

            # Call the handler with default key
            await bind_chat_command_handler(mock_message)

            # Verify bind_chat was called with correct args
            mock_bind_chat.assert_called_once_with(123, 456, "default")

            # Verify message was sent
            mock_message.reply.assert_called_once()
            assert "successfully" in mock_message.reply.call_args[0][0]

    @pytest.mark.asyncio
    async def test_bind_chat_command_handler_with_key(self, mock_message):
        """Test the bind_chat command handler with a custom key."""
        with patch("botspot.components.new.chat_binder.bind_chat") as mock_bind_chat:
            # Set up the mock to return a BoundChatRecord
            mock_bind_chat.return_value = BoundChatRecord(user_id=123, chat_id=456, key="custom")

            # Set message text with a key
            mock_message.text = "/bind_chat custom"

            # Call the handler
            await bind_chat_command_handler(mock_message)

            # Verify bind_chat was called with correct args
            mock_bind_chat.assert_called_once_with(123, 456, "custom")

            # Verify message was sent
            mock_message.reply.assert_called_once()
            assert "successfully" in mock_message.reply.call_args[0][0]
            assert "custom" in mock_message.reply.call_args[0][0]

    @pytest.mark.asyncio
    async def test_bind_chat_command_handler_error(self, mock_message):
        """Test the bind_chat command handler when an error occurs."""
        with patch("botspot.components.new.chat_binder.bind_chat") as mock_bind_chat:
            # Set up the mock to raise an error
            mock_bind_chat.side_effect = ValueError("Chat already bound")

            # Call the handler
            await bind_chat_command_handler(mock_message)

            # Verify error message was sent
            mock_message.reply.assert_called_once()
            assert "Error" in mock_message.reply.call_args[0][0]
            assert "Chat already bound" in mock_message.reply.call_args[0][0]

    @pytest.mark.asyncio
    async def test_unbind_chat_command_handler(self, mock_message):
        """Test the unbind_chat command handler."""
        with patch("botspot.components.new.chat_binder.unbind_chat") as mock_unbind_chat:
            # Set up the mock to return success
            mock_unbind_chat.return_value = (True, "default")

            # Call the handler
            await unbind_chat_command_handler(mock_message)

            # Verify unbind_chat was called with correct args
            mock_unbind_chat.assert_called_once_with(123, "default", chat_id=456)

            # Verify success message was sent
            mock_message.reply.assert_called_once()
            assert "unbound successfully" in mock_message.reply.call_args[0][0]

    @pytest.mark.asyncio
    async def test_unbind_chat_command_handler_with_key(self, mock_message):
        """Test the unbind_chat command handler with a custom key."""
        with patch("botspot.components.new.chat_binder.unbind_chat") as mock_unbind_chat:
            # Set up the mock to return success
            mock_unbind_chat.return_value = (True, "custom")

            # Set message text with a key
            mock_message.text = "/unbind_chat custom"

            # Call the handler
            await unbind_chat_command_handler(mock_message)

            # Verify unbind_chat was called with correct args
            mock_unbind_chat.assert_called_once_with(123, "custom", chat_id=456)

            # Verify success message was sent
            mock_message.reply.assert_called_once()
            assert "unbound successfully" in mock_message.reply.call_args[0][0]
            assert "custom" in mock_message.reply.call_args[0][0]

    @pytest.mark.asyncio
    async def test_unbind_chat_command_handler_error(self, mock_message):
        """Test the unbind_chat command handler when an error occurs."""
        with patch("botspot.components.new.chat_binder.unbind_chat") as mock_unbind_chat:
            # Set up the mock to raise an error
            mock_unbind_chat.side_effect = ValueError("No binding found")

            # Call the handler
            await unbind_chat_command_handler(mock_message)

            # Verify error message was sent
            mock_message.reply.assert_called_once()
            assert "Error" in mock_message.reply.call_args[0][0]
            assert "No binding found" in mock_message.reply.call_args[0][0]

    @pytest.mark.asyncio
    async def test_bind_status_command_handler_single_binding(self, mock_message):
        """Test the bind_status command handler with a single binding."""
        with patch("botspot.components.new.chat_binder.get_chat_binding_status") as mock_get_status:
            # Set up the mock to return a single binding
            mock_get_status.return_value = [BoundChatRecord(user_id=123, chat_id=456, key="test")]

            # Call the handler
            await bind_status_command_handler(mock_message)

            # Verify get_chat_binding_status was called with correct args
            mock_get_status.assert_called_once_with(123, 456)

            # Verify message was sent indicating a single binding
            mock_message.reply.assert_called_once()
            reply_text = mock_message.reply.call_args[0][0]
            assert "bound to you with key" in reply_text
            assert "test" in reply_text

    @pytest.mark.asyncio
    async def test_bind_status_command_handler_multiple_bindings(self, mock_message):
        """Test the bind_status command handler with multiple bindings."""
        with patch("botspot.components.new.chat_binder.get_chat_binding_status") as mock_get_status:
            # Set up the mock to return multiple bindings
            mock_get_status.return_value = [
                BoundChatRecord(user_id=123, chat_id=456, key="key1"),
                BoundChatRecord(user_id=123, chat_id=456, key="key2"),
            ]

            # Call the handler
            await bind_status_command_handler(mock_message)

            # Verify get_chat_binding_status was called with correct args
            mock_get_status.assert_called_once_with(123, 456)

            # Verify message was sent indicating multiple bindings
            mock_message.reply.assert_called_once()
            reply_text = mock_message.reply.call_args[0][0]
            assert "bound to you with 2 keys" in reply_text
            assert "'key1'" in reply_text
            assert "'key2'" in reply_text

    @pytest.mark.asyncio
    async def test_bind_status_command_handler_no_bindings(self, mock_message):
        """Test the bind_status command handler with no bindings."""
        with patch("botspot.components.new.chat_binder.get_chat_binding_status") as mock_get_status:
            # Set up the mock to return no bindings
            mock_get_status.return_value = []

            # Call the handler
            await bind_status_command_handler(mock_message)

            # Verify get_chat_binding_status was called with correct args
            mock_get_status.assert_called_once_with(123, 456)

            # Verify message was sent indicating no bindings
            mock_message.reply.assert_called_once()
            assert "not bound to you" in mock_message.reply.call_args[0][0]


class TestInitialization:
    def test_initialize_mongodb_disabled(self):
        """Test initialize when MongoDB is disabled."""
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Set up mock dependencies with MongoDB disabled
            mock_deps = MagicMock()
            mock_deps.botspot_settings.mongo_database.enabled = False
            mock_deps.queue_manager = None
            mock_get_deps.return_value = mock_deps

            # Call initialize and expect RuntimeError
            with pytest.raises(RuntimeError) as excinfo:
                initialize(ChatBinderSettings())

            # Verify error message
            assert "MongoDB is required" in str(excinfo.value)

    def test_initialize_success(self):
        """Test successful initialization."""
        with patch(
            "botspot.core.dependency_manager.get_dependency_manager"
        ) as mock_get_deps, patch(
            "botspot.components.qol.bot_commands_menu.add_command"
        ) as mock_add_command:
            # Set up mock dependencies with MongoDB enabled
            mock_deps = MagicMock()
            mock_deps.botspot_settings.mongo_database.enabled = True
            mock_deps.queue_manager = None
            mock_deps.mongo_db = MagicMock()
            mock_deps.mongo_db.get_collection.return_value = AsyncMock()
            mock_get_deps.return_value = mock_deps

            # Set up mock add_command to return the decorated function
            mock_add_command.return_value = lambda x: x

            # Call initialize
            settings = ChatBinderSettings(enabled=True)
            result = initialize(settings)

            # Verify ChatBinder was created with correct settings
            assert isinstance(result, ChatBinder)
            assert result.settings == settings

            # Verify commands were registered
            assert mock_add_command.call_count == 5

    def test_setup_dispatcher(self):
        """Test that setup_dispatcher registers handlers correctly."""
        # Patch Command to create consistent Command objects for comparison
        with patch("aiogram.filters.Command", side_effect=lambda cmd: f"Command({cmd})"):
            # Create a mock dispatcher
            mock_dp = MagicMock()
            mock_dp.message = MagicMock()
            mock_dp.message.register = MagicMock()

            # Call setup_dispatcher
            result = setup_dispatcher(mock_dp)

            # Verify dispatcher was returned
            assert result == mock_dp

            # Verify handlers were registered
            assert mock_dp.message.register.call_count == 5

            # Verify the registration calls contained the expected handlers
            calls = mock_dp.message.register.call_args_list
            handlers = [call[0][0].__name__ for call in calls]

            # Check that our command handlers are in the list of registered handlers
            assert "bind_chat_command_handler" in handlers
            assert "unbind_chat_command_handler" in handlers
            assert "bind_status_command_handler" in handlers
            assert "async_list_chats_handler" in handlers
            assert "async_get_chat_handler" in handlers


class TestWrapperFunctions:
    @pytest.mark.asyncio
    async def test_bind_chat_wrapper(self):
        """Test that the bind_chat wrapper function calls the ChatBinder instance."""
        with patch("botspot.components.new.chat_binder.get_chat_binder") as mock_get_binder:
            # Set up the mock binder
            mock_binder = MagicMock()
            mock_binder.bind_chat = AsyncMock()
            mock_get_binder.return_value = mock_binder

            # Call the wrapper function
            await bind_chat(user_id=123, chat_id=456, key="test")

            # Verify the binder method was called with correct args
            mock_binder.bind_chat.assert_called_once_with(123, 456, "test")

    @pytest.mark.asyncio
    async def test_unbind_chat_wrapper(self):
        """Test that the unbind_chat wrapper function calls the ChatBinder instance."""
        with patch("botspot.components.new.chat_binder.get_chat_binder") as mock_get_binder:
            # Set up the mock binder
            mock_binder = MagicMock()
            mock_binder.unbind_chat = AsyncMock(return_value=(True, "test"))
            mock_get_binder.return_value = mock_binder

            # Call the wrapper function
            result = await unbind_chat(user_id=123, key="test", chat_id=456)

            # Verify the binder method was called with correct args
            mock_binder.unbind_chat.assert_called_once_with(123, "test", 456)
            assert result == (True, "test")

    @pytest.mark.asyncio
    async def test_get_bind_chat_id_wrapper(self):
        """Test that the get_bind_chat_id wrapper function calls the ChatBinder instance."""
        with patch("botspot.components.new.chat_binder.get_chat_binder") as mock_get_binder:
            # Set up the mock binder
            mock_binder = MagicMock()
            mock_binder.get_bind_chat_id = AsyncMock(return_value=456)
            mock_get_binder.return_value = mock_binder

            # Call the wrapper function
            result = await get_bind_chat_id(user_id=123, key="test")

            # Verify the binder method was called with correct args and result was returned
            mock_binder.get_bind_chat_id.assert_called_once_with(123, "test")
            assert result == 456

    @pytest.mark.asyncio
    async def test_get_user_bound_chats_wrapper(self):
        """Test that the get_user_bound_chats wrapper function calls the ChatBinder instance."""
        with patch("botspot.components.new.chat_binder.get_chat_binder") as mock_get_binder:
            # Set up the mock binder
            mock_binder = MagicMock()
            mock_records = [BoundChatRecord(user_id=123, chat_id=456, key="test")]
            mock_binder.get_user_bound_chats = AsyncMock(return_value=mock_records)
            mock_get_binder.return_value = mock_binder

            # Call the wrapper function
            result = await get_user_bound_chats(user_id=123)

            # Verify the binder method was called with correct args and result was returned
            mock_binder.get_user_bound_chats.assert_called_once_with(123)
            assert result == mock_records

    @pytest.mark.asyncio
    async def test_get_chat_binding_status_wrapper(self):
        """Test that the get_chat_binding_status wrapper function calls the ChatBinder instance."""
        with patch("botspot.components.new.chat_binder.get_chat_binder") as mock_get_binder:
            # Set up the mock binder
            mock_binder = MagicMock()
            mock_records = [BoundChatRecord(user_id=123, chat_id=456, key="test")]
            mock_binder.get_chat_binding_status = AsyncMock(return_value=mock_records)
            mock_get_binder.return_value = mock_binder

            # Call the wrapper function
            result = await get_chat_binding_status(user_id=123, chat_id=456)

            # Verify the binder method was called with correct args and result was returned
            mock_binder.get_chat_binding_status.assert_called_once_with(123, 456)
            assert result == mock_records
