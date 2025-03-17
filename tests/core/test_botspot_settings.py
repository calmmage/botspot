import os
import pytest
from botspot.core.botspot_settings import BotspotSettings


class TestBotspotSettings:
    def test_default_settings(self):
        """Test default settings are initialized properly."""
        settings = BotspotSettings()
        
        # Test default admin and friends lists
        assert settings.admins == []
        assert settings.friends == []
        
        # Test component settings defaults
        assert settings.error_handling.enabled is True
        assert settings.bot_commands_menu.enabled is True
        assert settings.bot_info.enabled is True
        
    def test_admin_parsing(self):
        """Test parsing admin string into a list."""
        # Setup test data
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("BOTSPOT_ADMINS_STR", "@admin1, @admin2, @admin3")
            settings = BotspotSettings()
            
            # Test admin list
            assert settings.admins == ["@admin1", "@admin2", "@admin3"]
    
    def test_empty_admin_parsing(self):
        """Test parsing empty admin string."""
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("BOTSPOT_ADMINS_STR", "")
            settings = BotspotSettings()
            
            # Test empty list
            assert settings.admins == []
    
    def test_admin_parsing_with_spaces(self):
        """Test parsing admin string with extra spaces."""
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("BOTSPOT_ADMINS_STR", "  @admin1  ,@admin2,   @admin3  ")
            settings = BotspotSettings()
            
            # Test admin list with spaces removed
            assert settings.admins == ["@admin1", "@admin2", "@admin3"]
    
    def test_friends_parsing(self):
        """Test parsing friends string into a list."""
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("BOTSPOT_FRIENDS_STR", "@friend1, @friend2, @friend3")
            settings = BotspotSettings()
            
            # Test friends list
            assert settings.friends == ["@friend1", "@friend2", "@friend3"]
    
    def test_component_settings_override(self):
        """Test overriding component settings through environment variables."""
        with pytest.MonkeyPatch.context() as mp:
            # Override component settings
            mp.setenv("BOTSPOT_ERROR_HANDLING_ENABLED", "False")
            mp.setenv("BOTSPOT_BOT_INFO_ENABLED", "False")
            
            settings = BotspotSettings()
            
            # Test overridden settings
            assert settings.error_handling.enabled is False
            assert settings.bot_info.enabled is False
            # This one should still be true (default)
            assert settings.bot_commands_menu.enabled is True