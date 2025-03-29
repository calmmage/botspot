"""
Auto Archive component.

Forwards messages to a bound archive chat and deletes them from the original conversation to keep it clean.
"""

from typing import TYPE_CHECKING, Dict, Optional

from aiogram import Bot, F
from aiogram.filters import Command
from aiogram.types import Message
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorCollection  # noqa: F401

logger = get_logger()


class AutoArchiveSettings(BaseSettings):
    enabled: bool = False
    delete_delay: int = 0  # Delay before deletion in seconds, 0 means immediate
    collection_name: str = "auto_archive_config"
    commands_visible: bool = True

    class Config:
        env_prefix = "BOTSPOT_AUTO_ARCHIVE_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class ArchiveConfig(BaseModel):
    user_id: int
    chat_id: int  # Source chat to archive from
    archive_chat_id: int  # Destination chat to archive to
    is_active: bool = True


class AutoArchive:
    def __init__(self, settings: AutoArchiveSettings, collection: "AsyncIOMotorCollection"):
        self.settings = settings
        self.collection = collection
        self.configs: Dict[int, Dict[int, ArchiveConfig]] = {}
        
    async def load_configs(self):
        """Load all archive configurations from the database."""
        configs = await self.collection.find({}).to_list(length=None)
        for config in configs:
            user_id = config["user_id"]
            chat_id = config["chat_id"]
            if user_id not in self.configs:
                self.configs[user_id] = {}
            self.configs[user_id][chat_id] = ArchiveConfig(**config)
        
    async def bind_archive(self, user_id: int, chat_id: int, archive_chat_id: int) -> ArchiveConfig:
        """Bind a chat to an archive chat for a user."""
        config = ArchiveConfig(
            user_id=user_id,
            chat_id=chat_id,
            archive_chat_id=archive_chat_id,
        )
        
        # Save to in-memory cache
        if user_id not in self.configs:
            self.configs[user_id] = {}
        self.configs[user_id][chat_id] = config
        
        # Save to database
        await self.collection.update_one(
            {"user_id": user_id, "chat_id": chat_id},
            {"$set": config.model_dump()},
            upsert=True,
        )
        
        return config
    
    async def unbind_archive(self, user_id: int, chat_id: int) -> bool:
        """Unbind a chat from an archive chat for a user."""
        # Remove from in-memory cache
        if user_id in self.configs and chat_id in self.configs[user_id]:
            del self.configs[user_id][chat_id]
            if not self.configs[user_id]:
                del self.configs[user_id]
                
        # Remove from database
        result = await self.collection.delete_one({"user_id": user_id, "chat_id": chat_id})
        return result.deleted_count > 0
    
    async def get_config(self, user_id: int, chat_id: int) -> Optional[ArchiveConfig]:
        """Get the archive configuration for a user and chat."""
        # Check in-memory cache first
        if user_id in self.configs and chat_id in self.configs[user_id]:
            return self.configs[user_id][chat_id]
        
        # Check database if not in cache
        config_data = await self.collection.find_one({"user_id": user_id, "chat_id": chat_id})
        if config_data:
            config = ArchiveConfig(**config_data)
            if user_id not in self.configs:
                self.configs[user_id] = {}
            self.configs[user_id][chat_id] = config
            return config
        
        return None
    
    async def toggle_archive(self, user_id: int, chat_id: int) -> Optional[bool]:
        """Toggle the active status of an archive configuration."""
        config = await self.get_config(user_id, chat_id)
        if not config:
            return None
        
        config.is_active = not config.is_active
        await self.collection.update_one(
            {"user_id": user_id, "chat_id": chat_id},
            {"$set": {"is_active": config.is_active}}
        )
        return config.is_active


async def bind_archive_handler(message: Message, auto_archive: AutoArchive):
    """Handle the /bind_archive command."""
    if message.from_user is None:
        await message.reply("This command can only be used by users.")
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    command_parts = message.text.split() if message.text else []
    
    if len(command_parts) < 2:
        await message.reply("Usage: /bind_archive [archive_chat_id]")
        return
    
    try:
        archive_chat_id = int(command_parts[1])
    except ValueError:
        await message.reply("Archive chat ID must be a number.")
        return
    
    await auto_archive.bind_archive(user_id, chat_id, archive_chat_id)
    await message.reply(f"Chat bound successfully. Messages from this chat will be forwarded to chat {archive_chat_id}.")


async def unbind_archive_handler(message: Message, auto_archive: AutoArchive):
    """Handle the /unbind_archive command."""
    if message.from_user is None:
        await message.reply("This command can only be used by users.")
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    result = await auto_archive.unbind_archive(user_id, chat_id)
    if result:
        await message.reply("Archive binding removed successfully.")
    else:
        await message.reply("No archive binding found for this chat.")


async def toggle_archive_handler(message: Message, auto_archive: AutoArchive):
    """Handle the /toggle_archive command."""
    if message.from_user is None:
        await message.reply("This command can only be used by users.")
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    result = await auto_archive.toggle_archive(user_id, chat_id)
    if result is None:
        await message.reply("No archive binding found for this chat.")
    else:
        status = "activated" if result else "paused"
        await message.reply(f"Auto-archiving for this chat is now {status}.")


async def message_handler(message: Message, auto_archive: AutoArchive, bot: Bot):
    """Forward messages to archive chat and delete from original chat."""
    if message.from_user is None or message.chat is None:
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Check if there's an active archive config for this chat
    config = await auto_archive.get_config(user_id, chat_id)
    if not config or not config.is_active:
        return
    
    try:
        # Forward the message to the archive chat
        await bot.forward_message(
            chat_id=config.archive_chat_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
        
        # Delete the original message after the configured delay
        if auto_archive.settings.delete_delay > 0:
            import asyncio
            await asyncio.sleep(auto_archive.settings.delete_delay)
            
        await message.delete()
        logger.info(f"Archived message {message.message_id} from chat {chat_id} to {config.archive_chat_id}")
    except Exception as e:
        logger.error(f"Failed to archive message: {e}")


def setup_dispatcher(dp):
    """Register message handlers."""
    auto_archive = get_auto_archive()
    
    # Register command handlers
    dp.message.register(bind_archive_handler, Command("bind_archive"), auto_archive=auto_archive)
    dp.message.register(unbind_archive_handler, Command("unbind_archive"), auto_archive=auto_archive)
    dp.message.register(toggle_archive_handler, Command("toggle_archive"), auto_archive=auto_archive)
    
    # Register message handler with low priority to allow other handlers to process first
    dp.message.register(message_handler, F.chat.type.in_({"private", "group", "supergroup"}), auto_archive=auto_archive)
    
    return dp


def initialize(settings: AutoArchiveSettings) -> AutoArchive:
    """Initialize AutoArchive component."""
    from botspot.core.dependency_manager import get_dependency_manager
    from botspot.utils.deps_getters import get_database
    
    # Check that MongoDB is available
    deps = get_dependency_manager()
    if not deps.botspot_settings.mongo_database.enabled:
        raise RuntimeError("MongoDB is required for auto_archive component")
    
    # Register commands in the bot menu if needed
    if settings.commands_visible:
        from botspot.components.qol.bot_commands_menu import Visibility, add_command
        
        add_command("bind_archive", "Bind this chat to an archive chat", visibility=Visibility.PUBLIC)
        add_command("unbind_archive", "Unbind this chat from archive", visibility=Visibility.PUBLIC)
        add_command("toggle_archive", "Toggle auto-archiving for this chat", visibility=Visibility.PUBLIC)
    
    # Initialize the collection
    db = get_database()
    collection = db.get_collection(settings.collection_name)
    
    # Create instance and initialize configs
    auto_archive = AutoArchive(settings, collection)
    import asyncio
    
    # Create a task to load configs asynchronously
    asyncio.create_task(auto_archive.load_configs())
    
    logger.info(f"AutoArchive component initialized with collection {settings.collection_name}")
    return auto_archive


def get_auto_archive() -> AutoArchive:
    """Get AutoArchive instance from dependency manager."""
    from botspot.core.dependency_manager import get_dependency_manager
    
    deps = get_dependency_manager()
    return deps.auto_archive