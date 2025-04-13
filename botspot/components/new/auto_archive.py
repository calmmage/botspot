import asyncio
from enum import Enum
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, Set

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import Message
from loguru import logger
from pydantic_settings import BaseSettings

from botspot.commands_menu import Visibility, botspot_command
from botspot.utils.deps_getters import get_database
from botspot.utils.send_safe import send_safe

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorCollection  # noqa: F401


class CommandFilterMode(str, Enum):
    PURE_COMMANDS = (
        "pure_commands"  # delete only commands that have /command and NO OTHER TEXT
    )
    SINGLE_LINE = "single_line"  # delete only commands that are within one line
    ALL_COMMANDS = "all_commands"  # delete all commands, even multi-line


class AutoArchiveSettings(BaseSettings):
    enabled: bool = False
    delay: int = 10  # seconds
    enable_chat_handler: bool = False  # whether to add a general chat message handler
    private_chats_only: bool = True  # whether to only auto-archive in private chats
    chat_binding_key: str = "default"  # key to use for chat binding
    bind_command_visible: bool = (
        True  # whether the bind command should be visible in menu
    )
    no_archive_tag: str = "#noarchive"  # tag that prevents both forwarding and deletion
    no_delete_tag: str = "#nodelete"  # tag that prevents deletion but allows forwarding
    forward_sent_messages: bool = True  # whether to forward messages sent by the bot
    dont_forward_commands: bool = True  # whether to not forward commands
    command_filter_mode: CommandFilterMode = (
        CommandFilterMode.PURE_COMMANDS
    )  # how to filter commands

    class Config:
        env_prefix = "BOTSPOT_AUTO_ARCHIVE_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class AutoArchive(BaseMiddleware):
    def __init__(self, settings: AutoArchiveSettings) -> None:
        self.settings = settings
        self._intro_sent: Set[int] = set()
        self._warning_sent: Set[int] = set()
        self._collection = None

    async def _get_collection(self) -> "AsyncIOMotorCollection":
        if self._collection is None:
            db = get_database()
            self._collection = db["auto_archive_intro"]
        return self._collection

    async def _load_intro_sent(self) -> None:
        collection = await self._get_collection()
        cursor = collection.find({})
        async for doc in cursor:
            self._intro_sent.add(doc["user_id"])
            if doc.get("warning_sent", False):
                self._warning_sent.add(doc["user_id"])

    async def _save_intro_sent(self, user_id: int) -> None:
        collection = await self._get_collection()
        await collection.update_one(
            {"user_id": user_id}, {"$set": {"user_id": user_id}}, upsert=True
        )

    async def _save_warning_sent(self, user_id: int) -> None:
        collection = await self._get_collection()
        await collection.update_one(
            {"user_id": user_id},
            {"$set": {"user_id": user_id, "warning_sent": True}},
            upsert=True,
        )

    def _is_command(self, message: Message) -> bool:
        """Check if message is a command based on filter mode.

        Args:
            message: Message to check

        Returns:
            bool: True if message should be treated as a command
        """
        if not message.text:
            return False

        text = message.text.strip()

        if self.settings.command_filter_mode == CommandFilterMode.PURE_COMMANDS:
            # Only pure commands (no args)
            return text.startswith("/") and len(text.split()) == 1

        elif self.settings.command_filter_mode == CommandFilterMode.SINGLE_LINE:
            # Commands in single line
            return text.startswith("/") and "\n" not in text

        else:  # ALL_COMMANDS
            # All commands
            return text.startswith("/")

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

        # Check for tags
        message_text = message.text or ""
        message_text = message_text.lower()

        if self.settings.no_archive_tag in message_text:
            # Skip both forwarding and deletion
            return await handler(event, data)

        if self.settings.no_delete_tag in message_text:
            # Forward but don't delete
            should_delete = False
        else:
            should_delete = True

        # step 1: get the bound chat.
        from botspot.components.new.chat_binder import get_bound_chat, unbind_chat
        from botspot.core.errors import ChatBindingNotFoundError

        try:
            target_chat_id = await get_bound_chat(
                user_id, key=self.settings.chat_binding_key
            )
        except ChatBindingNotFoundError:
            # tell user to bind the chat
            if user_id not in self._warning_sent:
                message_text = "Auto-archive is enabled, but you don't have a bound chat for forwarding messages to."
                await send_safe(message.chat.id, message_text)
                self._warning_sent.add(user_id)
                await self._save_warning_sent(user_id)
            return await handler(event, data)

        # Send intro message if this is first time for this user
        if user_id not in self._intro_sent:
            intro_message = (
                "🔔 Auto-archive is enabled! Your messages will be forwarded and deleted after a short delay.\n"
                f"• Use {self.settings.no_archive_tag} to prevent both forwarding and deletion\n"
                f"• Use {self.settings.no_delete_tag} to forward but keep the original message\n"
                "Use /autoarchive_help for more info."
            )
            await send_safe(message.chat.id, intro_message)
            self._intro_sent.add(user_id)
            await self._save_intro_sent(user_id)

        # Check if this is a command and we should not forward it
        should_forward = not (
            self.settings.dont_forward_commands and self._is_command(message)
        )

        if should_forward:
            try:
                await message.forward(target_chat_id)
            except TelegramBadRequest as e:
                if "the message can't be forwarded" in str(e):
                    # Likely the group was upgraded to supergroup
                    await unbind_chat(user_id, key=self.settings.chat_binding_key)
                    message_text = (
                        "⚠️ The bound chat was upgraded to supergroup. "
                        "Please use /bind_auto_archive to bind the new supergroup."
                    )
                    await send_safe(message.chat.id, message_text)
                    return await handler(event, data)
                raise

        result = await handler(event, data)

        if should_delete:
            await asyncio.sleep(self.settings.delay)
            await message.delete()

        return result


def setup_dispatcher(dp):
    aa = get_auto_archive()
    logger.info("Setting up AutoArchive middleware")

    # load_state
    dp.startup.register(aa._load_intro_sent)
    dp.message.middleware(aa)

    # Add bind command
    @botspot_command(
        "bind_auto_archive",
        "Bind a chat for auto-archiving",
        visibility=Visibility.PUBLIC
        if aa.settings.bind_command_visible
        else Visibility.HIDDEN,
    )
    async def cmd_bind_auto_archive(message: Message):
        if message.from_user is None:
            return
        from botspot.chat_binder import bind_chat

        await bind_chat(
            message.from_user.id, message.chat.id, key=aa.settings.chat_binding_key
        )
        await send_safe(message.chat.id, "Chat bound for auto-archiving")

    dp.message.register(cmd_bind_auto_archive, Command("bind_auto_archive"))

    # Add help command
    @botspot_command(
        "help_autoarchive",
        "Show auto-archive help",
        visibility=Visibility.PUBLIC,
    )
    async def cmd_help_autoarchive(message: Message):
        help_text = (
            "🤖 Auto-Archive Help\n\n"
            "• Messages are automatically forwarded to your bound chat and deleted after a short delay\n"
            f"• Use {aa.settings.no_archive_tag} to prevent both forwarding and deletion\n"
            f"• Use {aa.settings.no_delete_tag} to forward but keep the original message\n"
            "• Use /bind_auto_archive to bind a chat for auto-archiving"
        )
        await send_safe(message.chat.id, help_text)

    dp.message.register(cmd_help_autoarchive, Command("help_autoarchive"))

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
        raise RuntimeError(
            "Chat Binder is not enabled. BOTSPOT_CHAT_BINDER_ENABLED=true in .env"
        )

    # Set auto-delete flag in send_safe settings if not explicitly set
    if deps.botspot_settings.send_safe.auto_delete_enabled is None:
        deps.botspot_settings.send_safe.auto_delete_enabled = True

    # Initialize auto archive and load intro sent state
    auto_archive = AutoArchive(settings)

    logger.info("AutoArchive component initialized")
    return auto_archive


def get_auto_archive() -> AutoArchive:
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    return deps.auto_archive
