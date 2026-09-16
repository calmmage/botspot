import pytest

from botspot.components.main.event_scheduler import EventSchedulerSettings, initialize
from tests.telegram import BotClient


class TestEventSchedulerSettings:
    def test_default_settings(self):
        with pytest.MonkeyPatch.context() as mp:
            mp.delenv("BOTSPOT_SCHEDULER_ENABLED", raising=False)
            mp.delenv("BOTSPOT_SCHEDULER_TIMEZONE", raising=False)
            settings = EventSchedulerSettings()
            assert settings.enabled is False
            assert settings.timezone == "UTC"

    def test_settings_from_env(self):
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("BOTSPOT_SCHEDULER_ENABLED", "True")
            mp.setenv("BOTSPOT_SCHEDULER_TIMEZONE", "Europe/London")
            settings = EventSchedulerSettings()
            assert settings.enabled is True
            assert settings.timezone == "Europe/London"


class TestInitialize:
    def test_initialize_disabled(self):
        assert initialize(EventSchedulerSettings(enabled=False)) is None

    def test_initialize_with_valid_timezone(self):
        scheduler = initialize(EventSchedulerSettings(enabled=True, timezone="Europe/London"))
        assert scheduler is not None
        assert "Europe/London" in str(scheduler.timezone)


@pytest.mark.asyncio
async def test_startup_starts_the_real_scheduler():
    client = BotClient(event_scheduler={"enabled": True, "timezone": "UTC"})
    await client.emit_startup()
    scheduler = client.manager.deps.scheduler
    try:
        assert scheduler.running
    finally:
        scheduler.shutdown(wait=False)
