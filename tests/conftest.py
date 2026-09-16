import pytest

from botspot.components.qol.bot_commands_menu import commands as bot_commands
from botspot.utils.internal import Singleton


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    """Isolated env: valid dummy token, no external services."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:AATestingTokenForBotspotNotReal")
    monkeypatch.setenv("BOTSPOT_ERROR_HANDLER_EASTER_EGGS", "false")
    monkeypatch.setenv("BOTSPOT_MONGO_DATABASE_ENABLED", "false")
    monkeypatch.setenv("BOTSPOT_POSTGRES_DATABASE_ENABLED", "false")
    monkeypatch.setenv("BOTSPOT_TELETHON_MANAGER_ENABLED", "false")
    monkeypatch.setenv("BOTSPOT_LLM_PROVIDER_ENABLED", "false")
    monkeypatch.setenv("BOTSPOT_S3_STORAGE_ENABLED", "false")


@pytest.fixture(autouse=True)
def clean_singleton():
    Singleton._instances = {}
    bot_commands.clear()
    yield
    Singleton._instances = {}
    bot_commands.clear()
