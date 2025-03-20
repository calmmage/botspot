import pytest

from botspot.components.qol.bot_info import BotInfoSettings


class TestBotInfoSettings:
    def test_default_settings(self):
        """Test default settings are initialized properly"""
        with pytest.MonkeyPatch.context() as mp:
            # Clear any existing environment variables
            mp.delenv("BOTSPOT_BOT_INFO_ENABLED", raising=False)
            mp.delenv("BOTSPOT_BOT_INFO_HIDE_COMMAND", raising=False)
            mp.delenv("BOTSPOT_BOT_INFO_SHOW_DETAILED_SETTINGS", raising=False)

            settings = BotInfoSettings()

            assert settings.enabled is True
            assert settings.hide_command is False
            assert settings.show_detailed_settings is True

    def test_settings_from_env(self):
        """Test that settings can be loaded from environment variables"""
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("BOTSPOT_BOT_INFO_ENABLED", "False")
            mp.setenv("BOTSPOT_BOT_INFO_HIDE_COMMAND", "True")
            mp.setenv("BOTSPOT_BOT_INFO_SHOW_DETAILED_SETTINGS", "False")

            settings = BotInfoSettings()

            assert settings.enabled is False
            assert settings.hide_command is True
            assert settings.show_detailed_settings is False
