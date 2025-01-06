from typing import TYPE_CHECKING, Optional
from zoneinfo import ZoneInfo

from aiogram import Dispatcher
from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler


logger = get_logger()


class EventSchedulerSettings(BaseSettings):
    enabled: bool = False
    timezone: str = "UTC"  # Add timezone setting

    class Config:
        env_prefix = "BOTSPOT_SCHEDULER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


def initialise(settings: EventSchedulerSettings) -> Optional["AsyncIOScheduler"]:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    if not settings.enabled:
        logger.info("Event scheduler is disabled.")
        return None

    try:
        # Create scheduler with configured timezone
        if settings.timezone:
            timezone = ZoneInfo(settings.timezone)
        else:
            timezone = None
        scheduler = AsyncIOScheduler(timezone=timezone)
        logger.info(f"Event scheduler initialized with timezone: {settings.timezone}")
        return scheduler
    except Exception as e:
        logger.warning(
            f"Failed to set timezone {settings.timezone}, falling back to local timezone: {e}"
        )
        return AsyncIOScheduler()


async def run_scheduler():
    from botspot.core.dependency_manager import get_dependency_manager

    scheduler = get_dependency_manager().scheduler
    if not scheduler:
        logger.info("Event scheduler is disabled.")
        return

    scheduler.start()
    logger.info(f"Event scheduler started with timezone: {scheduler.timezone}")


def setup_dispatcher(dp: Dispatcher):
    """Launch the scheduler."""
    dp.startup.register(run_scheduler)
