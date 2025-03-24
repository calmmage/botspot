"""Tests to ensure that each component example correctly uses environment variables."""

import os
import sys

import pytest

# Add the necessary paths for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))


def test_ask_user_env_vars():
    """Test that the ask_user component reads environment variables correctly."""
    from botspot.components.features.user_interactions import AskUserSettings

    with pytest.MonkeyPatch.context() as mp:
        # Set environment variables
        mp.setenv("BOTSPOT_ASK_USER_ENABLED", "True")
        mp.setenv("BOTSPOT_ASK_USER_DEFAULT_TIMEOUT", "60")

        # Initialize settings
        settings = AskUserSettings()

        # Verify settings
        assert settings.enabled is True
        assert settings.default_timeout == 60


def test_chat_binder_env_vars():
    """Test that the chat_binder component reads environment variables correctly."""
    from botspot.components.new.chat_binder import ChatBinderSettings

    with pytest.MonkeyPatch.context() as mp:
        # Set environment variables
        mp.setenv("BOTSPOT_CHAT_BINDER_ENABLED", "True")
        mp.setenv("BOTSPOT_CHAT_BINDER_MONGO_COLLECTION", "test_chat_binder")
        mp.setenv("BOTSPOT_CHAT_BINDER_COMMANDS_VISIBLE", "True")
        mp.setenv("BOTSPOT_CHAT_BINDER_REBIND_MODE", "error")

        # Initialize settings
        settings = ChatBinderSettings()

        # Verify settings
        assert settings.enabled is True
        assert settings.mongo_collection == "test_chat_binder"
        assert settings.commands_visible is True
        assert settings.rebind_mode == "error"


def test_llm_provider_env_vars():
    """Test that the llm_provider component reads environment variables correctly."""
    from botspot.components.new.llm_provider import LLMProviderSettings

    with pytest.MonkeyPatch.context() as mp:
        # Set environment variables
        mp.setenv("BOTSPOT_LLM_PROVIDER_ENABLED", "True")
        mp.setenv("BOTSPOT_LLM_PROVIDER_DEFAULT_MODEL", "claude-3.7")
        mp.setenv("BOTSPOT_LLM_PROVIDER_DEFAULT_TEMPERATURE", "0.5")
        mp.setenv("BOTSPOT_LLM_PROVIDER_DEFAULT_MAX_TOKENS", "2000")
        mp.setenv("BOTSPOT_LLM_PROVIDER_DEFAULT_TIMEOUT", "60")

        # Initialize settings
        settings = LLMProviderSettings()

        # Verify settings
        assert settings.enabled is True
        assert settings.default_model == "claude-3.7"
        assert settings.default_temperature == 0.5
        assert settings.default_max_tokens == 2000
        assert settings.default_timeout == 60


def test_error_handler_env_vars():
    """Test that the error_handler component reads environment variables correctly."""
    from botspot.components.middlewares.error_handler import ErrorHandlerSettings

    with pytest.MonkeyPatch.context() as mp:
        # Set environment variables
        mp.setenv("BOTSPOT_ERROR_HANDLER_ENABLED", "True")
        mp.setenv("BOTSPOT_ERROR_HANDLER_DEVELOPER_CHAT_ID", "123456789")
        mp.setenv("BOTSPOT_ERROR_HANDLER_EASTER_EGGS", "True")

        # Initialize settings
        settings = ErrorHandlerSettings()

        # Verify settings
        assert settings.enabled is True
        assert settings.developer_chat_id == 123456789
        assert settings.easter_eggs is True


def test_bot_commands_menu_env_vars():
    """Test that the bot_commands_menu component reads environment variables correctly."""
    from botspot.components.qol.bot_commands_menu import BotCommandsMenuSettings

    with pytest.MonkeyPatch.context() as mp:
        # Set environment variables
        mp.setenv("BOTSPOT_BOT_COMMANDS_MENU_ENABLED", "True")
        mp.setenv("BOTSPOT_BOT_COMMANDS_MENU_ADMIN_ID", "2")
        mp.setenv("BOTSPOT_BOT_COMMANDS_MENU_BOTSPOT_HELP", "False")

        # Initialize settings
        settings = BotCommandsMenuSettings()

        # Verify settings
        assert settings.enabled is True
        assert settings.admin_id == 2
        assert settings.botspot_help is False
