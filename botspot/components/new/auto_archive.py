import asyncio
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware, types
from aiogram.filters import Command
from aiogram.types import Message
from loguru import logger
from pydantic_settings import BaseSettings

from botspot.commands_menu import Visibility, botspot_command
from botspot.utils.send_safe import send_safe

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorCollection  # noqa: F401


class AutoArchiveSettings(BaseSettings):
    enabled: bool = False
    delay: int = 10  # seconds
    enable_chat_handler: bool = False  # whether to add a general chat message handler
    private_chats_only: bool = True  # whether to only auto-archive in private chats
    chat_binding_key: str = "default"  # key to use for chat binding
    bind_command_visible: bool = True  # whether the bind command should be visible in menu

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

        message = event

        # Check if this is a private chat if private_chats_only is enabled
        if self.settings.private_chats_only and message.chat.type != "private":
            # If not private and private_chats_only is enabled, just pass through to handler without auto-archiving
            return await handler(event, data)

        assert message.from_user is not None
        user_id = message.from_user.id

        # step 1: get the bound chat.
        from botspot.components.new.chat_binder import get_bound_chat
        from botspot.core.errors import ChatBindingNotFoundError

        try:
            target_chat_id = await get_bound_chat(user_id, key=self.settings.chat_binding_key)
        except ChatBindingNotFoundError:
            # tell user to bind the chat
            message_text = "Auto-archive is enabled, but you don't have a bound chat for forwarding messages to."
            await send_safe(message.chat.id, message_text)
            return await handler(event, data)

        forwarded = await message.forward(target_chat_id)

        result = await handler(event, data)
        await asyncio.sleep(self.settings.delay)
        await message.delete()
        return result


def setup_dispatcher(dp):
    aa = get_auto_archive()
    logger.info("Setting up AutoArchive middleware")

    dp.message.middleware(aa)

    # Add bind command
    @botspot_command(
        "bind_auto_archive",
        "Bind a chat for auto-archiving",
        visibility=Visibility.PUBLIC if aa.settings.bind_command_visible else Visibility.HIDDEN,
    )
    async def cmd_bind_auto_archive(message: Message):
        if message.from_user is None:
            return
        from botspot.chat_binder import bind_chat

        await bind_chat(message.from_user.id, message.chat.id, key=aa.settings.chat_binding_key)
        await send_safe(message.chat.id, "Chat bound for auto-archiving")

    dp.message.register(cmd_bind_auto_archive, Command("bind_auto_archive"))

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
