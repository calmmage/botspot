from unittest.mock import MagicMock, patch

import pytest
from aiogram import Bot, Dispatcher

from botspot.core.botspot_settings import BotspotSettings
from botspot.core.dependency_manager import DependencyManager, get_dependency_manager
from botspot.utils.internal import Singleton


@pytest.fixture(autouse=True)
def clean_singleton():
    """Reset the singleton instance before each test"""
    # Clear the singleton instances before each test
    Singleton._instances = {}
    yield
    # Clean up after the test
    Singleton._instances = {}


class TestDependencyManager:
    def test_singleton_pattern(self):
        """Test that DependencyManager follows singleton pattern"""
        mock_settings = MagicMock(spec=BotspotSettings)
        dm1 = DependencyManager(botspot_settings=mock_settings)
        dm2 = DependencyManager(botspot_settings=mock_settings)
        assert dm1 is dm2

    def test_initialization(self):
        """Test that DependencyManager can be initialized with dependencies"""
        mock_bot = MagicMock(spec=Bot)
        mock_dispatcher = MagicMock(spec=Dispatcher)
        mock_settings = MagicMock(spec=BotspotSettings)
        mock_db = MagicMock()

        # Initialize with dependencies
        dm = DependencyManager(
            botspot_settings=mock_settings,
            bot=mock_bot,
            dispatcher=mock_dispatcher,
            mongo_database=mock_db,
        )

        # Verify dependencies are set
        assert dm.botspot_settings is mock_settings
        assert dm.bot is mock_bot
        assert dm.dispatcher is mock_dispatcher
        assert dm.mongo_database is mock_db

    def test_property_setters(self):
        """Test that properties can be set after initialization"""
        mock_settings = MagicMock(spec=BotspotSettings)
        dm = DependencyManager(botspot_settings=mock_settings)

        # Create mock dependencies
        mock_bot = MagicMock(spec=Bot)
        mock_dispatcher = MagicMock(spec=Dispatcher)
        mock_db = MagicMock()
        mock_scheduler = MagicMock()
        mock_telethon_manager = MagicMock()
        mock_user_manager = MagicMock()

        # Set properties
        dm.bot = mock_bot
        dm.dispatcher = mock_dispatcher
        dm.mongo_database = mock_db
        dm.scheduler = mock_scheduler
        dm.telethon_manager = mock_telethon_manager
        dm.user_manager = mock_user_manager

        # Verify properties are set
        assert dm.bot is mock_bot
        assert dm.dispatcher is mock_dispatcher
        assert dm.mongo_database is mock_db
        assert dm.scheduler is mock_scheduler
        assert dm.telethon_manager is mock_telethon_manager
        assert dm.user_manager is mock_user_manager

    def test_custom_attributes(self):
        """Test that custom attributes can be set at initialization"""
        mock_settings = MagicMock(spec=BotspotSettings)
        dm = DependencyManager(botspot_settings=mock_settings, custom_service=MagicMock())
        assert hasattr(dm, "custom_service")

    def test_is_initialized(self):
        """Test is_initialized class method"""
        # Before initialization
        assert not DependencyManager.is_initialized()

        # After initialization
        mock_settings = MagicMock(spec=BotspotSettings)
        DependencyManager(botspot_settings=mock_settings)
        assert DependencyManager.is_initialized()

    def test_default_attributes(self):
        """Test that default attributes are set when not provided"""
        mock_settings = MagicMock(spec=BotspotSettings)
        dm = DependencyManager(botspot_settings=mock_settings)

        assert dm.botspot_settings is mock_settings
        # Check internal attributes directly instead of properties that raise exceptions
        assert dm._bot is None
        assert dm._dispatcher is None
        assert dm._mongo_database is None
        assert dm._scheduler is None
        assert dm._telethon_manager is None
        assert dm._user_manager is None

    def test_botspot_settings_initialization(self):
        """Test that botspot_settings is properly initialized"""
        mock_settings = MagicMock(spec=BotspotSettings)
        dm = DependencyManager(botspot_settings=mock_settings)

        # Check that the provided settings object is used
        assert dm.botspot_settings is mock_settings

    def test_multiple_dependency_instances(self):
        """Test that attributes from first instance persist in subsequent instances due to singleton"""
        # Reset Singleton for this test
        from botspot.utils.internal import Singleton

        Singleton._instances = {}

        # Create a fresh instance with settings
        mock_settings = MagicMock(spec=BotspotSettings)
        dm1 = DependencyManager(botspot_settings=mock_settings)
        mock_bot = MagicMock(spec=Bot)

        # Set a property on the first instance
        dm1.bot = mock_bot

        # Verify the first property is set
        assert dm1._bot is mock_bot

        # Both instances should be the same object due to singleton
        dm2 = DependencyManager(
            botspot_settings=MagicMock()
        )  # Different settings should be ignored due to singleton
        assert dm1 is dm2
        assert dm2._bot is mock_bot

        # Clean up after test
        Singleton._instances = {}


class TestGetDependencyManager:
    def test_get_uninitialized_manager(self):
        """Test that getting uninitialized manager raises ValueError"""
        with pytest.raises(ValueError, match="Dependency manager is not initialized"):
            get_dependency_manager()

    def test_get_initialized_manager(self):
        """Test that get_dependency_manager returns the singleton instance"""
        mock_settings = MagicMock(spec=BotspotSettings)
        dm = DependencyManager(botspot_settings=mock_settings)
        retrieved_dm = get_dependency_manager()
        assert retrieved_dm is dm

    def test_dependency_manager_functionality(self):
        """Test that get_dependency_manager returns a fully functional DependencyManager"""
        mock_settings = MagicMock(spec=BotspotSettings)
        mock_bot = MagicMock(spec=Bot)

        # Initialize with botspot_settings and bot
        DependencyManager(botspot_settings=mock_settings, bot=mock_bot)

        # Get the manager
        dm = get_dependency_manager()

        # Check the bot is set
        assert dm.bot is mock_bot

        # Test we can set new attributes
        mock_dispatcher = MagicMock(spec=Dispatcher)
        dm.dispatcher = mock_dispatcher

        # Get the manager again
        dm2 = get_dependency_manager()

        # Both attributes should be set
        assert dm2.bot is mock_bot
        assert dm2.dispatcher is mock_dispatcher
