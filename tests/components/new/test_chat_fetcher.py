"""ChatFetcher settings. Telethon I/O is out of process; no handler MagicMocks."""

import pytest

from botspot.components.new.chat_fetcher import ChatFetcherSettings


class TestChatFetcherSettings:
    def test_default_settings(self):
        with pytest.MonkeyPatch.context() as mp:
            mp.delenv("BOTSPOT_CHAT_FETCHER_ENABLED", raising=False)
            mp.delenv("BOTSPOT_CHAT_FETCHER_DB_CACHE_ENABLED", raising=False)
            settings = ChatFetcherSettings()
            assert settings.enabled is False
            assert settings.db_cache_enabled is False

    def test_settings_from_env(self):
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("BOTSPOT_CHAT_FETCHER_ENABLED", "True")
            mp.setenv("BOTSPOT_CHAT_FETCHER_DB_CACHE_ENABLED", "True")
            settings = ChatFetcherSettings()
            assert settings.enabled is True
            assert settings.db_cache_enabled is True
