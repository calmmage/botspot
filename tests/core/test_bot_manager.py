import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from aiogram import Bot, Dispatcher
from botspot.core.bot_manager import BotManager
from botspot.utils.internal import Singleton
from botspot.components.data.user_data import User


@pytest.fixture(autouse=True)
def clean_singleton():
    """Reset the singleton instance before each test"""
    # Clear the singleton instances before each test
    Singleton._instances = {}
    yield
    # Clean up after the test
    Singleton._instances = {}


class TestBotManager:
    def test_singleton_pattern(self):
        """Test that BotManager follows singleton pattern"""
        bm1 = BotManager()
        bm2 = BotManager()
        assert bm1 is bm2

    def test_initialization_without_parameters(self):
        """Test initialization without parameters"""
        with patch('botspot.core.bot_manager.BotspotSettings') as mock_settings_class, \
             patch('botspot.core.bot_manager.DependencyManager') as mock_deps_class, \
             patch('botspot.core.bot_manager.logger'):
            
            mock_settings = MagicMock()
            mock_settings_class.return_value = mock_settings
            
            mock_deps = MagicMock()
            mock_deps_class.return_value = mock_deps
            
            bm = BotManager()
            
            # Verify settings and deps are initialized
            assert bm.settings is mock_settings
            assert bm.deps is mock_deps
            assert bm.user_class is None
            
    def test_initialization_with_parameters(self):
        """Test initialization with bot, dispatcher, and user_class"""
        with patch('botspot.core.bot_manager.BotspotSettings') as mock_settings_class, \
             patch('botspot.core.bot_manager.DependencyManager') as mock_deps_class, \
             patch('botspot.core.bot_manager.logger'):
            
            mock_settings = MagicMock()
            mock_settings_class.return_value = mock_settings
            
            mock_deps = MagicMock()
            mock_deps_class.return_value = mock_deps
            
            # Create mock bot, dispatcher, and user_class
            mock_bot = MagicMock(spec=Bot)
            mock_dispatcher = MagicMock(spec=Dispatcher)
            
            class TestUser(User):
                pass
            
            bm = BotManager(bot=mock_bot, dispatcher=mock_dispatcher, user_class=TestUser)
            
            # Verify dependencies are passed to DependencyManager
            mock_deps_class.assert_called_once()
            assert mock_deps_class.call_args[1]['bot'] is mock_bot
            assert mock_deps_class.call_args[1]['dispatcher'] is mock_dispatcher
            
            # Verify user_class is set
            assert bm.user_class is TestUser
            
    @pytest.mark.parametrize(
        "component_name,enabled,expected_init_call,expected_setup_call",
        [
            ("mongo_database", True, True, True),
            ("mongo_database", False, False, False),
            ("event_scheduler", True, True, True),
            ("event_scheduler", False, False, False),
            ("telethon_manager", True, True, True),
            ("telethon_manager", False, False, False),
            ("user_data", True, True, True),
            ("user_data", False, False, False),
            ("single_user_mode", True, True, True),
            ("single_user_mode", False, False, False),
        ],
    )
    def test_component_initialization(self, component_name, enabled, expected_init_call, expected_setup_call):
        """Test component initialization based on settings"""
        with patch('botspot.core.bot_manager.BotspotSettings') as mock_settings_class, \
             patch('botspot.core.bot_manager.DependencyManager') as mock_deps_class, \
             patch(f'botspot.core.bot_manager.{component_name}') as mock_component, \
             patch('botspot.core.bot_manager.logger'):
            
            # Configure mock settings
            mock_settings = MagicMock()
            component_settings = MagicMock()
            component_settings.enabled = enabled
            # Use getattr dynamically to set the attribute
            setattr(mock_settings, component_name, component_settings)
            mock_settings_class.return_value = mock_settings
            
            # Configure mock deps
            mock_deps = MagicMock()
            mock_deps_class.return_value = mock_deps
            
            # Create BotManager
            bm = BotManager()
            
            # Check if component was initialized
            if expected_init_call:
                mock_component.initialize.assert_called_once()
            else:
                mock_component.initialize.assert_not_called()
                
            # Check setup_dispatcher
            mock_dispatcher = MagicMock()
            bm.setup_dispatcher(mock_dispatcher)
            
            # Check if component.setup_dispatcher was called
            if expected_setup_call:
                mock_component.setup_dispatcher.assert_called_once()
            else:
                mock_component.setup_dispatcher.assert_not_called()
            
    def test_ask_user_requires_bot(self):
        """Test that ask_user setup raises an error if bot is not set"""
        with patch('botspot.core.bot_manager.BotspotSettings') as mock_settings_class, \
             patch('botspot.core.bot_manager.DependencyManager') as mock_deps_class, \
             patch('botspot.core.bot_manager.logger'):
            
            # Configure mock settings
            mock_settings = MagicMock()
            ask_user_settings = MagicMock()
            ask_user_settings.enabled = True
            mock_settings.ask_user = ask_user_settings
            mock_settings_class.return_value = mock_settings
            
            # Configure mock deps with no bot
            mock_deps = MagicMock()
            mock_deps.bot = None
            mock_deps_class.return_value = mock_deps
            
            # Create BotManager
            bm = BotManager()
            
            # Setup dispatcher should raise an error for ask_user
            mock_dispatcher = MagicMock()
            with pytest.raises(RuntimeError, match="Bot instance is required for ask_user functionality"):
                bm.setup_dispatcher(mock_dispatcher)