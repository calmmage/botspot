import asyncio
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware, types
from aiogram.types import Message
from loguru import logger
from pydantic_settings import BaseSettings

from botspot.utils.send_safe import send_safe

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorCollection  # noqa: F401


class AutoArchiveSettings(BaseSettings):
    enabled: bool = False
    delay: int = 10  # seconds
    enable_chat_handler: bool = False  # whether to add a general chat message handler

    # todo:
    #  add bind_chat_key config
    # bound_chat_key: str = "auto-archive"
    #  add a flag to add special command e.g. /bind_auto_archive

    class Config:
        env_prefix = "BOTSPOT_AUTO_ARCHIVE_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class AutoArchive(BaseMiddleware):
    def __init__(self, settings: AutoArchiveSettings) -> None:
        self.settings = settings

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        logger.debug("AutoArchive middleware called")

        # data['counter'] = self.counter
        message = event
        user_id = message.from_user.id

        # step 1: get the bound chat.
        from botspot.components.new.chat_binder import get_bound_chat
        from botspot.core.errors import ChatBindingNotFoundError

        try:
            target_chat_id = await get_bound_chat(user_id)
        except ChatBindingNotFoundError:
            # tell user to bind the chat
            message = "Auto-archive is enabled, but you don't have a bound chat for forwarding messages to."
            await send_safe(user_id, message)
            return await handler(event, data)

        forwarded = await message.forward(target_chat_id)

        # before:
        # return await handler(event, data)

        result = await handler(event, data)
        await asyncio.sleep(self.settings.delay)
        await message.delete()
        return result

        # return await handler(event, data)
        # async def new_handler(message: Message, data: Dict[str, Any]):
        #     await handler(message, data)
        #     # Optional delay (e.g., 1 second) to let the user see the message
        #     await asyncio.sleep(self.settings.delay)  # Configurable delay
        #
        #     # Delete the original message from the bot chat
        #     await message.delete()
        #
        # return await new_handler(message, data)


def setup_dispatcher(dp):
    aa = get_auto_archive()
    logger.info("Setting up AutoArchive middleware")

    dp.message.middleware(aa)

    # Add general chat message handler if enabled
    if aa.settings.enable_chat_handler:

        @dp.message()
        async def general_chat_handler(message: Message):
            # This handler does nothing but activates the auto-archive middleware
            pass

    return dp


def initialize(settings: AutoArchiveSettings) -> AutoArchive:
    """Initialize the AutoArchive component.

    Args:
        settings: Configuration for the AutoArchive component

    Returns:
        AutoArchive instance

    Raises:
        RuntimeError: If chat_binder component is not enabled
    """
    if not settings.enabled:
        logger.info("AutoArchive component is disabled")
        return AutoArchive(settings)

    # Check that chat_binder component is enabled
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()

    if not deps.botspot_settings.chat_binder.enabled:
        logger.error("Chat Binder is not enabled. AutoArchive component requires it.")
        raise RuntimeError("Chat Binder is not enabled. BOTSPOT_CHAT_BINDER_ENABLED=true in .env")

    logger.info("AutoArchive component initialized")
    return AutoArchive(settings)


def get_auto_archive() -> AutoArchive:
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    return deps.auto_archive
