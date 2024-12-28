"""
Getters for all deps attributes

Provides utility functions to access dependencies from the dependency manager.
Each getter:
- Gets the dependency manager instance
- Retrieves the requested dependency
- Validates it is not None
- Returns the typed dependency
- explains how to enable the dependency if it is not initialized
"""

from typing import Optional

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telethon import TelegramClient


def get_bot() -> Bot:
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    bot: Bot = deps.bot
    assert (
            bot is not None
    ), "Bot is not initialized. To enable pass bot instance to BotManager() constructor"
    return bot


def get_scheduler() -> AsyncIOScheduler:
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    scheduler: AsyncIOScheduler = deps.scheduler
    assert (
            scheduler is not None
    ), "Scheduler is not initialized. To enable set ENABLE_SCHEDULER or pass enable_scheduler=True into botspot config"
    return scheduler


def get_telethon_client(user_id: int) -> Optional[TelegramClient]:
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    telethon_manager = deps.telethon_manager
    assert (
            telethon_manager is not None
    ), "TelethonManager is not initialized. To enable set ENABLE_TELETHON_MANAGER or pass enable_telethon_manager=True into botspot config"
    return telethon_manager.get_client(user_id)
