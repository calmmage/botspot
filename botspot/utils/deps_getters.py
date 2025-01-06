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

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from aiogram import Bot
    from aiogram.fsm.context import FSMContext
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from motor.motor_asyncio import AsyncIOMotorDatabase
    from telethon import TelegramClient

    from botspot.components.telethon_manager import TelethonManager


def get_bot() -> "Bot":
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    bot: "Bot" = deps.bot
    assert (
        bot is not None
    ), "Bot is not initialized. To enable pass bot instance to BotManager() constructor"
    return bot


def get_scheduler() -> "AsyncIOScheduler":
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    scheduler: "AsyncIOScheduler" = deps.scheduler
    assert (
        scheduler is not None
    ), "Scheduler is not initialized. To enable set ENABLE_SCHEDULER or pass enable_scheduler=True into botspot config"
    return scheduler


def get_telethon_manager() -> "TelethonManager":
    """Get the TelethonManager instance from dependency manager"""
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    if not deps.telethon_manager:
        raise RuntimeError(
            "TelethonManager is not initialized. Make sure it's enabled in settings."
        )
    return deps.telethon_manager


async def get_telethon_client(
    user_id: int, state: Optional["FSMContext"] = None
) -> "TelegramClient":
    """
    Get a TelegramClient instance for a specific user.
    If state is provided and auto_auth is enabled, will trigger authentication if client is missing.
    """
    telethon_manager = get_telethon_manager()
    client = await telethon_manager.get_client(user_id, state)
    if not client:
        raise RuntimeError(
            f"No active Telethon client found for user {user_id}. Use /setup_telethon to create one."
        )
    return client


def get_database() -> "AsyncIOMotorDatabase":
    """Get MongoDB database instance from dependency manager."""
    from botspot.core.dependency_manager import get_dependency_manager

    db = get_dependency_manager().mongo_database
    if db is None:
        raise RuntimeError("MongoDB is not initialized")
    return db
