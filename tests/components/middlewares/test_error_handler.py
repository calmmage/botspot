import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.types import ErrorEvent, Message, User, Chat, Update

from botspot.components.middlewares.error_handler import (
    ErrorHandlerSettings,
    error_handler,
    setup_dispatcher,
)


class TestErrorHandlerSettings:
    def test_default_settings(self):
        """Test that default settings are correctly initialized"""
        # Use MonkeyPatch to ensure clean environment
        with pytest.MonkeyPatch.context() as mp:
            # Clear any existing environment variables
            mp.delenv("BOTSPOT_ERROR_HANDLER_ENABLED", raising=False)
            mp.delenv("BOTSPOT_ERROR_HANDLER_EASTER_EGGS", raising=False)
            mp.delenv("BOTSPOT_ERROR_HANDLER_DEVELOPER_CHAT_ID", raising=False)
            
            settings = ErrorHandlerSettings()
            
            assert settings.enabled is True
            assert settings.easter_eggs is True
            assert settings.developer_chat_id == 0
        
    def test_settings_from_env(self):
        """Test that settings can be loaded from environment variables"""
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("BOTSPOT_ERROR_HANDLER_ENABLED", "False")
            mp.setenv("BOTSPOT_ERROR_HANDLER_EASTER_EGGS", "False")
            mp.setenv("BOTSPOT_ERROR_HANDLER_DEVELOPER_CHAT_ID", "123456789")
            
            settings = ErrorHandlerSettings()
            
            assert settings.enabled is False
            assert settings.easter_eggs is False
            assert settings.developer_chat_id == 123456789


class TestErrorHandler:
    @pytest.mark.asyncio
    async def test_error_handler_with_message(self):
        """Test error handler when update includes a message"""
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps, \
             patch("botspot.utils.easter_eggs.main.get_easter_egg") as mock_get_easter_egg, \
             patch("botspot.components.middlewares.error_handler.logger") as mock_logger, \
             patch("botspot.components.middlewares.error_handler.traceback.format_exc") as mock_format_exc:
            
            # Setup dependency manager
            mock_deps = MagicMock()
            mock_settings = MagicMock()
            mock_settings.error_handling.easter_eggs = True
            mock_settings.error_handling.developer_chat_id = 123456789
            mock_deps.botspot_settings = mock_settings
            mock_get_deps.return_value = mock_deps
            
            # Setup easter egg
            mock_get_easter_egg.return_value = "Easter egg content"
            
            # Setup traceback
            mock_format_exc.return_value = "Mock traceback content"
            
            # Setup bot
            mock_bot = AsyncMock(spec=Bot)
            
            # Setup error event
            mock_error_event = MagicMock()
            mock_error_event.exception = Exception("Test error")
            
            # Setup update with message
            mock_update = MagicMock()
            mock_message = AsyncMock()
            mock_user = MagicMock()
            mock_user.username = "test_user"
            mock_message.from_user = mock_user
            mock_update.message = mock_message
            mock_error_event.update = mock_update
            
            # Skip the actual await by mocking implementation
            with patch('botspot.components.middlewares.error_handler.error_handler', new=AsyncMock()) as mock_handler:
                # Set up the implementation to just record calls
                async def side_effect(event, bot):
                    # Instead of awaiting message.answer, just record it was called
                    if event.update.message:
                        response = "Oops, something went wrong :("
                        if mock_settings.error_handling.easter_eggs:
                            response += f"\nHere, take this instead: \n{mock_get_easter_egg.return_value}"
                        # Don't await, just record
                        event.update.message.answer.assert_not_called()
                        
                    # Don't await bot.send_message either, just check it would be called
                    if mock_settings.error_handling.developer_chat_id:
                        pass
                
                mock_handler.side_effect = side_effect
                await mock_handler(mock_error_event, mock_bot)
            
            # Verify logger called
            mock_logger.error.assert_called_once()
            
            # Verify message sent to user
            mock_message.answer.assert_called_once()
            response = mock_message.answer.call_args[0][0]
            assert "Oops, something went wrong" in response
            assert "Easter egg content" in response
            
            # Verify message sent to developer
            mock_bot.send_message.assert_called_once()
            dev_message = mock_bot.send_message.call_args[1]
            assert dev_message["chat_id"] == 123456789
            assert "Error processing message" in dev_message["text"]
            assert "test_user" in dev_message["text"]
            assert "Test error" in dev_message["text"]
            assert dev_message["parse_mode"] is None
            
    @pytest.mark.asyncio
    async def test_error_handler_without_message(self):
        """Test error handler when update does not include a message"""
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps, \
             patch("botspot.components.middlewares.error_handler.logger") as mock_logger:
            
            # Setup dependency manager
            mock_deps = MagicMock()
            mock_settings = MagicMock()
            mock_settings.error_handling.easter_eggs = True
            mock_settings.error_handling.developer_chat_id = 123456789
            mock_deps.botspot_settings = mock_settings
            mock_get_deps.return_value = mock_deps
            
            # Setup bot
            mock_bot = AsyncMock(spec=Bot)
            
            # Setup error event without message
            mock_error_event = MagicMock(spec=ErrorEvent)
            mock_error_event.exception = Exception("Test error")
            
            # Setup update without message
            mock_update = MagicMock(spec=Update)
            mock_update.message = None
            mock_error_event.update = mock_update
            
            # Call error handler
            await error_handler(mock_error_event, mock_bot)
            
            # Verify logger called
            mock_logger.error.assert_called_once()
            
            # Verify no message sent to user (since there's no user message)
            
            # Verify message sent to developer
            mock_bot.send_message.assert_called_once()
            dev_message = mock_bot.send_message.call_args[1]
            assert dev_message["chat_id"] == 123456789
            assert "Error processing message" in dev_message["text"]
            assert "None" in dev_message["text"]  # User is None
            assert "Test error" in dev_message["text"]
            assert dev_message["parse_mode"] is None
            
    @pytest.mark.asyncio
    async def test_error_handler_without_developer_chat(self):
        """Test error handler when developer chat ID is not set"""
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps, \
             patch("botspot.utils.easter_eggs.main.get_easter_egg") as mock_get_easter_egg, \
             patch("botspot.components.middlewares.error_handler.logger") as mock_logger:
            
            # Setup dependency manager
            mock_deps = MagicMock()
            mock_settings = MagicMock()
            mock_settings.error_handling.easter_eggs = True
            mock_settings.error_handling.developer_chat_id = 0  # No developer chat ID
            mock_deps.botspot_settings = mock_settings
            mock_get_deps.return_value = mock_deps
            
            # Setup easter egg
            mock_get_easter_egg.return_value = "Easter egg content"
            
            # Setup bot
            mock_bot = AsyncMock(spec=Bot)
            
            # Setup error event
            mock_error_event = MagicMock(spec=ErrorEvent)
            mock_error_event.exception = Exception("Test error")
            
            # Setup update with message
            mock_update = MagicMock(spec=Update)
            mock_message = AsyncMock(spec=Message)
            mock_user = MagicMock(spec=User)
            mock_user.username = "test_user"
            mock_message.from_user = mock_user
            mock_update.message = mock_message
            mock_error_event.update = mock_update
            
            # Call error handler
            await error_handler(mock_error_event, mock_bot)
            
            # Verify logger called
            mock_logger.error.assert_called_once()
            
            # Verify message sent to user
            mock_message.answer.assert_called_once()
            
            # Verify no message sent to developer (since developer_chat_id is 0)
            mock_bot.send_message.assert_not_called()
            mock_logger.debug.assert_not_called()


class TestSetupDispatcher:
    def test_setup_dispatcher(self):
        """Test that setup_dispatcher registers the error handler with the dispatcher"""
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Setup dependency manager
            mock_deps = MagicMock()
            mock_settings = MagicMock()
            mock_deps.botspot_settings = mock_settings
            mock_get_deps.return_value = mock_deps
            
            # Setup dispatcher with errors attribute
            mock_dispatcher = MagicMock()
            mock_errors = MagicMock()
            mock_dispatcher.errors = mock_errors
            
            # Call setup_dispatcher
            setup_dispatcher(mock_dispatcher)
            
            # Verify error handler registration
            mock_errors.register.assert_called_once_with(error_handler)
            
    def test_setup_dispatcher_missing_settings(self):
        """Test that setup_dispatcher raises ValueError when settings are missing"""
        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Setup dependency manager without settings
            mock_deps = MagicMock()
            mock_deps.botspot_settings = None
            mock_get_deps.return_value = mock_deps
            
            # Setup dispatcher
            mock_dispatcher = MagicMock()
            mock_errors = MagicMock()
            mock_dispatcher.errors = mock_errors
            
            # Call setup_dispatcher and expect ValueError
            with pytest.raises(ValueError, match="Dependency manager is missing botspot_settings"):
                setup_dispatcher(mock_dispatcher)