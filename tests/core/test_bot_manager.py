from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram import Bot, Dispatcher

from botspot.components.data.user_data import User
from botspot.core.bot_manager import BotManager
from botspot.utils.internal import Singleton


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
        with patch("botspot.core.bot_manager.BotspotSettings") as mock_settings_class, patch(
            "botspot.core.bot_manager.DependencyManager"
        ) as mock_deps_class, patch(
            "botspot.core.bot_manager.telethon_manager"
        ) as mock_telethon_manager, patch(
            "botspot.core.bot_manager.user_data"
        ) as mock_user_data, patch(
            "botspot.core.bot_manager.chat_binder"
        ) as mock_chat_binder, patch(
            "botspot.core.bot_manager.logger"
        ):

            # Configure mock settings with all components disabled
            mock_settings = MagicMock()
            for component in [
                "telethon_manager",
                "mongo_database",
                "event_scheduler",
                "user_data",
                "single_user_mode",
                "chat_binder",
            ]:
                component_settings = MagicMock()
                component_settings.enabled = False
                setattr(mock_settings, component, component_settings)

            mock_settings_class.return_value = mock_settings

            # Mock components to avoid real initialization
            mock_telethon_manager.initialize.return_value = None
            mock_user_data.initialize.return_value = None
            mock_chat_binder.initialize.return_value = None

            bm1 = BotManager()
            bm2 = BotManager()
            assert bm1 is bm2

    def test_initialization_without_parameters(self):
        """Test initialization without parameters"""
        with patch("botspot.core.bot_manager.BotspotSettings") as mock_settings_class, patch(
            "botspot.core.bot_manager.telethon_manager"
        ) as mock_telethon_manager, patch(
            "botspot.core.bot_manager.user_data"
        ) as mock_user_data, patch(
            "botspot.core.bot_manager.chat_binder"
        ) as mock_chat_binder, patch(
            "botspot.core.bot_manager.logger"
        ), patch(
            "botspot.core.bot_manager.DependencyManager"
        ) as mock_deps_class:

            mock_settings = MagicMock()
            # Configure mock settings with all components disabled
            for component in [
                "telethon_manager",
                "mongo_database",
                "event_scheduler",
                "user_data",
                "single_user_mode",
                "chat_binder",
            ]:
                component_settings = MagicMock()
                component_settings.enabled = False
                setattr(mock_settings, component, component_settings)
            mock_settings_class.return_value = mock_settings

            mock_deps = MagicMock()
            mock_deps_class.return_value = mock_deps

            # Mock components to avoid real initialization
            mock_telethon_manager.initialize.return_value = None
            mock_user_data.initialize.return_value = None
            mock_chat_binder.initialize.return_value = None

            bm = BotManager()

            # Verify settings and deps are initialized
            assert bm.settings is mock_settings
            assert bm.deps is mock_deps
            assert bm.user_class is None

    def test_initialization_with_parameters(self):
        """Test initialization with bot, dispatcher, and user_class"""
        with patch("botspot.core.bot_manager.BotspotSettings") as mock_settings_class, patch(
            "botspot.core.bot_manager.DependencyManager"
        ) as mock_deps_class, patch(
            "botspot.core.bot_manager.telethon_manager"
        ) as mock_telethon_manager, patch(
            "botspot.core.bot_manager.user_data"
        ) as mock_user_data, patch(
            "botspot.core.bot_manager.chat_binder"
        ) as mock_chat_binder, patch(
            "botspot.core.bot_manager.logger"
        ):

            mock_settings = MagicMock()
            # Configure mock settings with all components disabled
            for component in [
                "telethon_manager",
                "mongo_database",
                "event_scheduler",
                "user_data",
                "single_user_mode",
                "chat_binder",
            ]:
                component_settings = MagicMock()
                component_settings.enabled = False
                setattr(mock_settings, component, component_settings)
            mock_settings_class.return_value = mock_settings

            mock_deps = MagicMock()
            mock_deps_class.return_value = mock_deps

            # Mock components to avoid real initialization
            mock_telethon_manager.initialize.return_value = None
            mock_user_data.initialize.return_value = None
            mock_chat_binder.initialize.return_value = None

            # Create mock bot, dispatcher, and user_class
            mock_bot = MagicMock(spec=Bot)
            mock_dispatcher = MagicMock(spec=Dispatcher)

            class TestUser(User):
                pass

            bm = BotManager(bot=mock_bot, dispatcher=mock_dispatcher, user_class=TestUser)

            # Verify dependencies are passed to DependencyManager
            mock_deps_class.assert_called_once()
            assert mock_deps_class.call_args[1]["bot"] is mock_bot
            assert mock_deps_class.call_args[1]["dispatcher"] is mock_dispatcher

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
    def test_component_initialization(
        self, component_name, enabled, expected_init_call, expected_setup_call
    ):
        """Test component initialization based on settings"""
        # Create patch objects for all components except the one we're testing
        patches = {}
        for comp in [
            "mongo_database",
            "event_scheduler",
            "telethon_manager",
            "user_data",
            "single_user_mode",
            "chat_binder",
        ]:
            if comp != component_name:
                patches[comp] = patch(f"botspot.core.bot_manager.{comp}")

        # Add patches for other dependencies
        patches.update(
            {
                "BotspotSettings": patch("botspot.core.bot_manager.BotspotSettings"),
                "DependencyManager": patch("botspot.core.bot_manager.DependencyManager"),
                "error_handler": patch("botspot.core.bot_manager.error_handler"),
                "trial_mode": patch("botspot.core.bot_manager.trial_mode"),
                "print_bot_url": patch("botspot.core.bot_manager.print_bot_url"),
                "bot_commands_menu": patch("botspot.core.bot_manager.bot_commands_menu"),
                "user_interactions": patch("botspot.core.bot_manager.user_interactions"),
                "bot_info": patch("botspot.core.bot_manager.bot_info"),
                "logger": patch("botspot.core.bot_manager.logger"),
                "get_dependency_manager": patch(
                    "botspot.core.dependency_manager.get_dependency_manager"
                ),
            }
        )

        # Start all patches and the component we're testing separately
        mocks = {}
        for name, p in patches.items():
            mocks[name] = p.start()

        # Patch the component we're testing separately
        component_patch = patch(f"botspot.core.bot_manager.{component_name}")
        mock_component = component_patch.start()

        # Configure mongo_database.initialize to return a tuple of (client, db) if we're testing it
        if component_name == "mongo_database":
            mock_client, mock_db = MagicMock(), MagicMock()
            mock_component.initialize.return_value = (mock_client, mock_db)

        try:
            # Configure mock settings
            mock_settings = MagicMock()

            # Disable all components by default
            for comp_name in [
                "error_handling",
                "telethon_manager",
                "mongo_database",
                "event_scheduler",
                "user_data",
                "single_user_mode",
                "chat_binder",
                "trial_mode",
                "print_bot_url",
                "bot_commands_menu",
                "ask_user",
                "bot_info",
            ]:
                comp_settings = MagicMock()
                comp_settings.enabled = False
                setattr(mock_settings, comp_name, comp_settings)

            # Configure the component we're testing
            component_settings = MagicMock()
            component_settings.enabled = enabled
            setattr(mock_settings, component_name, component_settings)
            mocks["BotspotSettings"].return_value = mock_settings

            # Configure mock deps
            mock_deps = MagicMock()
            mock_deps.botspot_settings = mock_settings
            mocks["DependencyManager"].return_value = mock_deps
            mocks["DependencyManager"].is_initialized.return_value = True
            mocks["get_dependency_manager"].return_value = mock_deps

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
                mock_component.setup_dispatcher.assert_called_once_with(mock_dispatcher)
            else:
                mock_component.setup_dispatcher.assert_not_called()

        finally:
            # Stop all patches
            for p in patches.values():
                p.stop()
            component_patch.stop()

    def test_ask_user_requires_bot(self):
        """Test that ask_user setup raises an error if bot is not set"""
        # Mock all the components that might be accessed in bot_manager.py
        with patch("botspot.core.bot_manager.BotspotSettings") as mock_settings_class, patch(
            "botspot.core.bot_manager.DependencyManager"
        ) as mock_deps_class, patch(
            "botspot.core.bot_manager.telethon_manager"
        ) as mock_telethon_manager, patch(
            "botspot.core.bot_manager.user_data"
        ) as mock_user_data, patch(
            "botspot.core.bot_manager.chat_binder"
        ) as mock_chat_binder, patch(
            "botspot.core.bot_manager.user_interactions"
        ) as mock_user_interactions, patch(
            "botspot.core.bot_manager.error_handler"
        ) as mock_error_handler, patch(
            "botspot.core.bot_manager.trial_mode"
        ) as mock_trial_mode, patch(
            "botspot.core.bot_manager.mongo_database"
        ) as mock_mongo_database, patch(
            "botspot.core.bot_manager.print_bot_url"
        ) as mock_print_bot_url, patch(
            "botspot.core.bot_manager.bot_commands_menu"
        ) as mock_bot_commands_menu, patch(
            "botspot.core.bot_manager.bot_info"
        ) as mock_bot_info, patch(
            "botspot.core.bot_manager.logger"
        ):

            # Configure mock settings
            mock_settings = MagicMock()

            # Disable all components by default
            for comp_name in [
                "error_handling",
                "telethon_manager",
                "mongo_database",
                "event_scheduler",
                "user_data",
                "single_user_mode",
                "chat_binder",
                "trial_mode",
                "print_bot_url",
                "bot_commands_menu",
                "bot_info",
            ]:
                comp_settings = MagicMock()
                comp_settings.enabled = False
                setattr(mock_settings, comp_name, comp_settings)

            # Enable ask_user only
            ask_user_settings = MagicMock()
            ask_user_settings.enabled = True
            mock_settings.ask_user = ask_user_settings
            mock_settings_class.return_value = mock_settings

            # Configure mock deps with no bot
            mock_deps = MagicMock()
            mock_deps.bot = None
            mock_deps.botspot_settings = mock_settings
            mock_deps_class.return_value = mock_deps
            mock_deps_class.is_initialized.return_value = True

            # Mock dependency_manager in all components
            with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
                mock_get_deps.return_value = mock_deps

                # Create BotManager
                bm = BotManager()

                # Setup dispatcher should raise an error for ask_user
                mock_dispatcher = MagicMock()
                with pytest.raises(
                    RuntimeError, match="Bot instance is required for ask_user functionality"
                ):
                    bm.setup_dispatcher(mock_dispatcher)
