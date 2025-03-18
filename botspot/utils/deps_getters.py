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
    from aiogram import Bot, Dispatcher
    from aiogram.fsm.context import FSMContext
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase  # noqa: F401
    from telethon import TelegramClient

    from botspot.components.main.telethon_manager import TelethonManager


def get_bot() -> "Bot":
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    bot: "Bot" = deps.bot
    assert (
        bot is not None
    ), "Bot is not initialized. To enable pass bot instance to BotManager() constructor"
    return bot


def get_dispatcher() -> "Dispatcher":
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    dispatcher: "Dispatcher" = deps.dispatcher
    assert (
        dispatcher is not None
    ), "Dispatcher is not initialized. To enable pass dispatcher instance to BotManager() constructor"
    return dispatcher


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


def get_mongo_client() -> "AsyncIOMotorClient":
    """Get MongoDB client instance from dependency manager."""
    from botspot.core.dependency_manager import get_dependency_manager

    client = get_dependency_manager().mongo_client
    if client is None:
        raise RuntimeError(
            "MongoDB client is not initialized. Make sure MongoDB is enabled in settings."
        )
    return client


def get_database() -> "AsyncIOMotorDatabase":
    """Get MongoDB database instance from dependency manager."""
    from botspot.core.dependency_manager import get_dependency_manager

    db = get_dependency_manager().mongo_database
    if db is None:
        raise RuntimeError(
            "MongoDB database is not initialized. Make sure MongoDB is enabled in settings."
        )
    return db


def get_user_manager():
    """Get UserManager instance from dependency manager."""
    from botspot.core.dependency_manager import get_dependency_manager

    user_manager = get_dependency_manager().user_manager
    if user_manager is None:
        raise RuntimeError(
            "UserManager is not initialized. Make sure user_data component is enabled in settings."
        )
    return user_manager
