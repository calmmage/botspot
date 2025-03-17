import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
from aiogram.types import Message

from botspot.components.qol.bot_info import (
    BotInfoSettings,
    bot_info_handler,
    setup_dispatcher,
    _start_time,
)


class TestBotInfoSettings:
    def test_default_settings(self):
        """Test default settings"""
        settings = BotInfoSettings()
        
        assert settings.enabled is True
        assert settings.hide_command is False
        assert settings.show_detailed_settings is True
        
    def test_settings_from_env(self):
        """Test settings from environment variables"""
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("BOTSPOT_BOT_INFO_ENABLED", "False")
            mp.setenv("BOTSPOT_BOT_INFO_HIDE_COMMAND", "True")
            mp.setenv("BOTSPOT_BOT_INFO_SHOW_DETAILED_SETTINGS", "False")
            
            settings = BotInfoSettings()
            
            assert settings.enabled is False
            assert settings.hide_command is True
            assert settings.show_detailed_settings is False


class TestBotInfoHandler:
    @pytest.mark.asyncio
    async def test_bot_info_handler_basic_info(self):
        """Test bot_info_handler includes basic info"""
        with patch('botspot.components.qol.bot_info.get_dependency_manager') as mock_get_deps, \
             patch('botspot.components.qol.bot_info.botspot.__version__', '0.4.10'):
            
            # Mock dependencies
            mock_deps = MagicMock()
            mock_settings = MagicMock()
            mock_settings.bot_info.enabled = True
            mock_settings.bot_info.show_detailed_settings = False
            
            # Setup field dict for iteration in the handler
            mock_settings.model_fields = {
                'component1': MagicMock(),
                'component2': MagicMock()
            }
            
            # Mock components
            component1 = MagicMock()
            component1.enabled = True
            component2 = MagicMock()
            component2.enabled = False
            
            setattr(mock_settings, 'component1', component1)
            setattr(mock_settings, 'component2', component2)
            
            mock_deps.botspot_settings = mock_settings
            mock_get_deps.return_value = mock_deps
            
            # Mock message
            mock_message = AsyncMock(spec=Message)
            
            # Call handler
            await bot_info_handler(mock_message)
            
            # Verify response
            mock_message.answer.assert_called_once()
            response = mock_message.answer.call_args[0][0]
            
            # Check if response contains expected info
            assert "🤖 Bot Information" in response
            assert "Botspot Version: 0.4.10" in response
            assert "📊 Enabled Components:" in response
            assert "✅ component1" in response
            assert "❌ component2" in response
            
            # Detailed settings should not be included
            assert "📊 Detailed Settings:" not in response
            
    @pytest.mark.asyncio
    async def test_bot_info_handler_detailed_settings(self):
        """Test bot_info_handler includes detailed settings when enabled"""
        with patch('botspot.components.qol.bot_info.get_dependency_manager') as mock_get_deps, \
             patch('botspot.components.qol.bot_info.botspot.__version__', '0.4.10'):
            
            # Mock dependencies
            mock_deps = MagicMock()
            mock_settings = MagicMock()
            mock_settings.bot_info.enabled = True
            mock_settings.bot_info.show_detailed_settings = True
            
            # Setup field dict for iteration in the handler
            mock_settings.model_fields = {}
            
            # Mock model_dump_json method
            mock_settings.model_dump_json.return_value = '{"key": "value"}'
            
            mock_deps.botspot_settings = mock_settings
            mock_get_deps.return_value = mock_deps
            
            # Mock message
            mock_message = AsyncMock(spec=Message)
            
            # Call handler
            await bot_info_handler(mock_message)
            
            # Verify response
            mock_message.answer.assert_called_once()
            response = mock_message.answer.call_args[0][0]
            
            # Check if response contains detailed settings
            assert "📊 Detailed Settings:" in response
            assert '{"key": "value"}' in response
            
    @pytest.mark.asyncio
    async def test_bot_info_handler_disabled(self):
        """Test bot_info_handler returns early if disabled"""
        with patch('botspot.components.qol.bot_info.get_dependency_manager') as mock_get_deps:
            
            # Mock dependencies
            mock_deps = MagicMock()
            mock_settings = MagicMock()
            mock_settings.bot_info.enabled = False
            
            mock_deps.botspot_settings = mock_settings
            mock_get_deps.return_value = mock_deps
            
            # Mock message
            mock_message = AsyncMock(spec=Message)
            
            # Call handler
            await bot_info_handler(mock_message)
            
            # Verify no response was sent
            mock_message.answer.assert_not_called()
            
    @pytest.mark.asyncio
    async def test_uptime_calculation(self):
        """Test uptime calculation in bot_info_handler"""
        with patch('botspot.components.qol.bot_info.get_dependency_manager') as mock_get_deps, \
             patch('botspot.components.qol.bot_info.datetime') as mock_datetime, \
             patch('botspot.components.qol.bot_info._start_time', datetime(2023, 1, 1, 0, 0, 0)), \
             patch('botspot.components.qol.bot_info.botspot.__version__', '0.4.10'):
            
            # Set current time to 1 day, 2 hours, 30 minutes after start
            current_time = datetime(2023, 1, 2, 2, 30, 0)
            mock_datetime.now.return_value = current_time
            
            # Mock dependencies
            mock_deps = MagicMock()
            mock_settings = MagicMock()
            mock_settings.bot_info.enabled = True
            mock_settings.bot_info.show_detailed_settings = False
            
            # Setup field dict for iteration in the handler
            mock_settings.model_fields = {}
            
            mock_deps.botspot_settings = mock_settings
            mock_get_deps.return_value = mock_deps
            
            # Mock message
            mock_message = AsyncMock(spec=Message)
            
            # Call handler
            await bot_info_handler(mock_message)
            
            # Verify response
            mock_message.answer.assert_called_once()
            response = mock_message.answer.call_args[0][0]
            
            # Check if response contains expected uptime
            assert "Uptime: 1d 2h 30m" in response


class TestSetupDispatcher:
    def test_setup_dispatcher_registers_handler(self):
        """Test setup_dispatcher registers the bot_info_handler"""
        with patch('botspot.components.qol.bot_info.get_dependency_manager') as mock_get_deps, \
             patch('botspot.components.qol.bot_info.add_command') as mock_add_command:
            
            # Mock dependencies
            mock_deps = MagicMock()
            mock_settings = MagicMock()
            mock_settings.bot_info.enabled = True
            mock_settings.bot_info.hide_command = False
            
            mock_deps.botspot_settings = mock_settings
            mock_get_deps.return_value = mock_deps
            
            # Mock dispatcher
            mock_dispatcher = MagicMock()
            
            # Call setup_dispatcher
            setup_dispatcher(mock_dispatcher)
            
            # Verify handler registration
            mock_dispatcher.message.register.assert_called_once()
            
            # Verify command was added
            mock_add_command.assert_called_once()
            
    def test_setup_dispatcher_with_hidden_command(self):
        """Test setup_dispatcher doesn't register command when hidden"""
        with patch('botspot.components.qol.bot_info.get_dependency_manager') as mock_get_deps, \
             patch('botspot.components.qol.bot_info.add_command') as mock_add_command:
            
            # Mock dependencies
            mock_deps = MagicMock()
            mock_settings = MagicMock()
            mock_settings.bot_info.enabled = True
            mock_settings.bot_info.hide_command = True
            
            mock_deps.botspot_settings = mock_settings
            mock_get_deps.return_value = mock_deps
            
            # Mock dispatcher
            mock_dispatcher = MagicMock()
            
            # Call setup_dispatcher
            setup_dispatcher(mock_dispatcher)
            
            # Verify handler registration
            mock_dispatcher.message.register.assert_called_once()
            
            # Verify command was not added
            mock_add_command.assert_not_called()
            
    def test_setup_dispatcher_disabled(self):
        """Test setup_dispatcher doesn't register anything when disabled"""
        with patch('botspot.components.qol.bot_info.get_dependency_manager') as mock_get_deps:
            
            # Mock dependencies
            mock_deps = MagicMock()
            mock_settings = MagicMock()
            mock_settings.bot_info.enabled = False
            
            mock_deps.botspot_settings = mock_settings
            mock_get_deps.return_value = mock_deps
            
            # Mock dispatcher
            mock_dispatcher = MagicMock()
            
            # Call setup_dispatcher
            setup_dispatcher(mock_dispatcher)
            
            # Verify no registrations
            mock_dispatcher.message.register.assert_not_called()