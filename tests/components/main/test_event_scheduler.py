import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from zoneinfo import ZoneInfo

from botspot.components.main.event_scheduler import (
    EventSchedulerSettings, 
    initialize, 
    run_scheduler, 
    setup_dispatcher
)


class TestEventSchedulerSettings:
    def test_default_settings(self):
        """Test default settings are correctly initialized"""
        with pytest.MonkeyPatch.context() as mp:
            # Clear any existing environment variables
            mp.delenv("BOTSPOT_SCHEDULER_ENABLED", raising=False)
            mp.delenv("BOTSPOT_SCHEDULER_TIMEZONE", raising=False)
            
            settings = EventSchedulerSettings()
            
            assert settings.enabled is False
            assert settings.timezone == "UTC"
            
    def test_settings_from_env(self):
        """Test that settings can be loaded from environment variables"""
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("BOTSPOT_SCHEDULER_ENABLED", "True")
            mp.setenv("BOTSPOT_SCHEDULER_TIMEZONE", "Europe/London")
            
            settings = EventSchedulerSettings()
            
            assert settings.enabled is True
            assert settings.timezone == "Europe/London"


class TestInitialize:
    def test_initialize_disabled(self):
        """Test initialize when scheduler is disabled"""
        with patch('botspot.components.main.event_scheduler.logger') as mock_logger:
            settings = EventSchedulerSettings(enabled=False)
            
            result = initialize(settings)
            
            assert result is None
            mock_logger.info.assert_called_once_with("Event scheduler is disabled.")
            
    def test_initialize_with_valid_timezone(self):
        """Test initialize with valid timezone"""
        with patch('apscheduler.schedulers.asyncio.AsyncIOScheduler') as mock_scheduler_class, \
             patch('botspot.components.main.event_scheduler.logger') as mock_logger:
            
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler
            
            
            settings = EventSchedulerSettings(enabled=True, timezone="Europe/London")
            
            result = initialize(settings)
            
            assert result is mock_scheduler
            mock_scheduler_class.assert_called_once()
            mock_logger.info.assert_called_once_with("Event scheduler initialized with timezone: Europe/London")
            
    def test_initialize_with_timezone_exception(self):
        """Test initialize when timezone raises exception"""
        with patch('apscheduler.schedulers.asyncio.AsyncIOScheduler') as mock_scheduler_class, \
             patch('botspot.components.main.event_scheduler.logger') as mock_logger, \
             patch('zoneinfo.ZoneInfo', side_effect=Exception("Invalid timezone")) as mock_zoneinfo:
            
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler
            
            
            settings = EventSchedulerSettings(enabled=True, timezone="Invalid/Timezone")
            
            result = initialize(settings)
            
            assert result is mock_scheduler
            mock_scheduler_class.assert_called_once() 
            mock_logger.warning.assert_called_once()  # Warning was logged


class TestRunScheduler:
    @pytest.mark.asyncio
    async def test_run_scheduler_enabled(self):
        """Test run_scheduler when scheduler is enabled"""
        with patch('botspot.core.dependency_manager.get_dependency_manager') as mock_get_deps, \
             patch('botspot.components.main.event_scheduler.logger') as mock_logger:
            
            # Setup mock scheduler
            mock_scheduler = MagicMock()
            mock_scheduler.timezone = "Europe/London"
            
            # Setup dependency manager
            mock_deps = MagicMock()
            mock_deps.scheduler = mock_scheduler
            mock_get_deps.return_value = mock_deps
            
            # Call run_scheduler
            await run_scheduler()
            
            # Verify scheduler was started
            mock_scheduler.start.assert_called_once()
            mock_logger.info.assert_called_once_with("Event scheduler started with timezone: Europe/London")
            
    @pytest.mark.asyncio
    async def test_run_scheduler_disabled(self):
        """Test run_scheduler when scheduler is disabled"""
        with patch('botspot.core.dependency_manager.get_dependency_manager') as mock_get_deps, \
             patch('botspot.components.main.event_scheduler.logger') as mock_logger:
            
            # Setup dependency manager with no scheduler
            mock_deps = MagicMock()
            mock_deps.scheduler = None
            mock_get_deps.return_value = mock_deps
            
            # Call run_scheduler
            await run_scheduler()
            
            # Verify scheduler was not started
            mock_logger.info.assert_called_once_with("Event scheduler is disabled.")


class TestSetupDispatcher:
    def test_setup_dispatcher(self):
        """Test that setup_dispatcher registers run_scheduler with startup"""
        # Setup dispatcher
        mock_dispatcher = MagicMock()
        mock_startup = MagicMock()
        mock_dispatcher.startup = mock_startup
        
        # Call setup_dispatcher
        setup_dispatcher(mock_dispatcher)
        
        # Verify run_scheduler was registered
        mock_startup.register.assert_called_once_with(run_scheduler)