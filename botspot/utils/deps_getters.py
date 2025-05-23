"""
Getters for all deps attributes

Provides utility functions to access dependencies from the dependency manager.
This module compiles all the getter functions from their respective component files.
"""

from typing import TYPE_CHECKING, Optional

# Import component getters
from botspot.components.data.mongo_database import get_database, get_mongo_client
from botspot.components.data.user_data import get_user_manager
from botspot.components.main.event_scheduler import get_scheduler
from botspot.components.middlewares.simple_user_cache import get_simple_user_cache
from botspot.components.main.single_user_mode import get_single_user, is_single_user_mode_enabled
from botspot.components.main.telethon_manager import get_telethon_manager
from botspot.components.new.chat_binder import get_chat_binder
from botspot.components.new.chat_fetcher import get_chat_fetcher
from botspot.components.new.llm_provider import get_llm_provider
from botspot.components.new.queue_manager import get_queue_manager
from botspot.components.new.s3_storage import S3StorageProvider
from botspot.utils.user_ops import to_user_record

if TYPE_CHECKING:
    from aiogram import Bot, Dispatcher
    from aiogram.fsm.context import FSMContext
    from telethon import TelegramClient


# Core getters for bot and dispatcher
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


# Define get_telethon_client here to avoid circular imports
async def get_telethon_client(
    user_id: Optional[int] = None, state: Optional["FSMContext"] = None
) -> "TelegramClient":
    """
    Get a TelegramClient instance for a specific user.
    If state is provided and auto_auth is enabled, will trigger authentication if client is missing.
    """
    telethon_manager = get_telethon_manager()
    if user_id is None:
        # assume single user mode
        if not is_single_user_mode_enabled():
            raise ValueError("user_id is required in single user mode")
        user = get_single_user()
        assert user is not None
        # todo: verify this flow works correctly
        user_id = to_user_record(user).user_id
        assert user_id is not None
    client = await telethon_manager.get_client(user_id, state)
    if not client:
        from botspot.core.errors import TelethonClientNotConnectedError

        raise TelethonClientNotConnectedError(
            f"No active Telethon client found for user {user_id}. Use /setup_telethon to create one."
        )
    return client


def get_s3_storage() -> Optional[S3StorageProvider]:
    """Get the S3 Storage provider from dependency manager."""
    from botspot.core.dependency_manager import get_dependency_manager

    return get_dependency_manager().s3_storage


# Re-export all for convenience
__all__ = [
    "get_bot",
    "get_dispatcher",
    "get_database",
    "get_user_manager",
    "get_scheduler",
    "get_telethon_manager",
    "get_telethon_client",
    "get_mongo_client",
    "get_chat_binder",
    "get_chat_fetcher",
    "get_queue_manager",
    "get_llm_provider",
    "get_s3_storage",
    "get_simple_user_cache",
]
