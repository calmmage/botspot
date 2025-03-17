from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from aiogram import Dispatcher
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorCollection
    from telethon import TelegramClient

logger = get_logger()


class ChatFetcherSettings(BaseSettings):
    enabled: bool = False
    cache_enabled: bool = True
    collection_name: str = "telegram_messages"
    max_messages_per_request: int = 100

    class Config:
        env_prefix = "BOTSPOT_CHAT_FETCHER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class ChatModel(BaseModel):
    """Basic model for storing chat information"""

    id: int
    title: str
    username: Optional[str] = None
    type: str = "private"  # private, group, channel, etc.
    last_message_date: Optional[datetime] = None


class MessageModel(BaseModel):
    """Basic model for storing message information"""

    id: int
    chat_id: int
    text: Optional[str] = None
    date: datetime
    from_id: Optional[int] = None
    reply_to_message_id: Optional[int] = None
    media: bool = False
    media_type: Optional[str] = None
    file_path: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatFetcher:
    """Component for fetching and caching Telegram chats and messages"""

    def __init__(
        self,
        settings: ChatFetcherSettings,
        collection: Optional["AsyncIOMotorCollection"] = None,
        single_user_id: Optional[str] = None,
    ):
        self.settings = settings
        self.collection = collection
        self.single_user_id = single_user_id
        logger.info(f"ChatFetcher initialized with cache_enabled={settings.cache_enabled}")

    async def get_client(self, user_id: Optional[int] = None) -> "TelegramClient":
        """Get telethon client for the specified user or for single user mode"""
        from botspot.components.main.telethon_manager import get_telethon_manager
        from botspot.core.dependency_manager import get_dependency_manager

        deps = get_dependency_manager()
        telethon_manager = get_telethon_manager()

        # If user_id is not provided and single user mode is enabled, use the single user
        if user_id is None:
            if not deps.botspot_settings.single_user_mode.enabled:
                raise ValueError("User ID must be provided when not in single user mode")
            user = deps.botspot_settings.single_user_mode.user
            # Convert username to numeric ID if needed
            if user.startswith("@"):
                # TODO: Implement username to ID conversion
                raise NotImplementedError("Username conversion not implemented yet")
            user_id = int(user)

        return await telethon_manager.get_client(user_id)

    async def get_chats(self, user_id: Optional[int] = None, limit: int = 100) -> List[ChatModel]:
        """Get chats for the specified user or for single user mode"""
        client = await self.get_client(user_id)

        # Get dialogs from Telethon
        dialogs = await client.get_dialogs(limit=limit)

        # Convert to ChatModel
        chats = []
        for dialog in dialogs:
            entity = dialog.entity

            # Determine chat type
            chat_type = "private"
            if hasattr(entity, "megagroup") and entity.megagroup:
                chat_type = "group"
            elif hasattr(entity, "broadcast") and entity.broadcast:
                chat_type = "channel"

            chat = ChatModel(
                id=dialog.id,
                title=dialog.title,
                username=getattr(entity, "username", None),
                type=chat_type,
                last_message_date=dialog.date,
            )
            chats.append(chat)

            # Cache the chat if caching is enabled
            if self.settings.cache_enabled and self.collection:
                await self._cache_chat(chat)

        return chats

    async def find_chat(
        self, query: str, user_id: Optional[int] = None, limit: int = 5
    ) -> List[ChatModel]:
        """Find chats by title or username"""
        # First try to get from cache
        if self.settings.cache_enabled and self.collection:
            cached_chats = await self._find_chats_in_cache(query, limit)
            if cached_chats:
                return cached_chats

        # If not found in cache, get all chats and filter
        chats = await self.get_chats(user_id, limit=100)  # Get more to search through

        # Filter by title or username
        query = query.lower()
        filtered_chats = [
            chat
            for chat in chats
            if (query in chat.title.lower() or (chat.username and query in chat.username.lower()))
        ]

        return filtered_chats[:limit]

    async def get_messages(
        self,
        chat_id: int,
        user_id: Optional[int] = None,
        limit: int = 100,
        offset_id: int = 0,
        min_id: Optional[int] = None,
        max_id: Optional[int] = None,
        reverse: bool = False,
    ) -> List[MessageModel]:
        """Get messages from a specific chat"""
        client = await self.get_client(user_id)

        # Try to get from cache first if appropriate
        if (
            self.settings.cache_enabled
            and self.collection
            and not min_id
            and not max_id
            and offset_id == 0
        ):
            cached_messages = await self._get_cached_messages(chat_id, limit)
            if cached_messages:
                return cached_messages

        # Limit the number of messages per request
        limit = min(limit, self.settings.max_messages_per_request)

        # Get messages from Telethon
        messages = await client.get_messages(
            chat_id, limit=limit, offset_id=offset_id, min_id=min_id, max_id=max_id, reverse=reverse
        )

        # Convert to MessageModel
        result = []
        for msg in messages:
            # Determine media type
            media_type = None
            has_media = False

            if hasattr(msg, "media") and msg.media:
                has_media = True
                media_type = type(msg.media).__name__

            message = MessageModel(
                id=msg.id,
                chat_id=chat_id,
                text=msg.text if hasattr(msg, "text") else None,
                date=msg.date,
                from_id=msg.from_id.user_id if hasattr(msg, "from_id") and msg.from_id else None,
                reply_to_message_id=(
                    msg.reply_to.reply_to_msg_id
                    if hasattr(msg, "reply_to") and msg.reply_to
                    else None
                ),
                media=has_media,
                media_type=media_type,
            )
            result.append(message)

            # Cache the message if caching is enabled
            if self.settings.cache_enabled and self.collection:
                await self._cache_message(message)

        return result

    async def find_messages(
        self,
        query: str,
        chat_id: int,
        user_id: Optional[int] = None,
        limit: int = 5,
        search_in_cached: bool = True,
    ) -> List[MessageModel]:
        """Find messages by text content"""
        # First try to search in cache
        if search_in_cached and self.settings.cache_enabled and self.collection:
            cached_messages = await self._find_messages_in_cache(query, chat_id, limit)
            if cached_messages:
                return cached_messages

        # If not found in cache, use telethon's search function
        client = await self.get_client(user_id)
        messages = await client.get_messages(chat_id, search=query, limit=limit)

        # Convert to MessageModel
        result = []
        for msg in messages:
            # Determine media type
            media_type = None
            has_media = False

            if hasattr(msg, "media") and msg.media:
                has_media = True
                media_type = type(msg.media).__name__

            message = MessageModel(
                id=msg.id,
                chat_id=chat_id,
                text=msg.text if hasattr(msg, "text") else None,
                date=msg.date,
                from_id=msg.from_id.user_id if hasattr(msg, "from_id") and msg.from_id else None,
                reply_to_message_id=(
                    msg.reply_to.reply_to_msg_id
                    if hasattr(msg, "reply_to") and msg.reply_to
                    else None
                ),
                media=has_media,
                media_type=media_type,
            )
            result.append(message)

            # Cache the message if caching is enabled
            if self.settings.cache_enabled and self.collection:
                await self._cache_message(message)

        return result

    async def download_media(
        self,
        message_id: int,
        chat_id: int,
        user_id: Optional[int] = None,
        target_path: Optional[Union[str, Path]] = None,
    ) -> Optional[str]:
        """Download media from a message"""
        client = await self.get_client(user_id)

        # Get the message
        message = await client.get_messages(chat_id, ids=message_id)

        if not message or not message.media:
            return None

        # Download the media
        file_path = await message.download(file=target_path)

        # Update the cache with file path
        if self.settings.cache_enabled and self.collection and file_path:
            await self._update_message_file_path(message_id, chat_id, str(file_path))

        return str(file_path) if file_path else None

    # Cache-related methods
    async def _cache_chat(self, chat: ChatModel) -> None:
        """Cache chat information"""
        if not self.collection:
            return

        try:
            # Check if the chat already exists
            existing = await self.collection.find_one({"type": "chat", "chat_id": chat.id})

            chat_dict = chat.dict()
            chat_dict["type"] = "chat"
            chat_dict["chat_id"] = chat.id

            if existing:
                # Update existing chat
                await self.collection.update_one(
                    {"type": "chat", "chat_id": chat.id}, {"$set": chat_dict}
                )
            else:
                # Insert new chat
                await self.collection.insert_one(chat_dict)

        except Exception as e:
            logger.error(f"Error caching chat: {e}")

    async def _cache_message(self, message: MessageModel) -> None:
        """Cache message information"""
        if not self.collection:
            return

        try:
            # Check if the message already exists
            existing = await self.collection.find_one(
                {"type": "message", "message_id": message.id, "chat_id": message.chat_id}
            )

            msg_dict = message.dict()
            msg_dict["type"] = "message"
            msg_dict["message_id"] = message.id

            if existing:
                # Update existing message
                await self.collection.update_one(
                    {"type": "message", "message_id": message.id, "chat_id": message.chat_id},
                    {"$set": msg_dict},
                )
            else:
                # Insert new message
                await self.collection.insert_one(msg_dict)

        except Exception as e:
            logger.error(f"Error caching message: {e}")

    async def _update_message_file_path(
        self, message_id: int, chat_id: int, file_path: str
    ) -> None:
        """Update file path in cached message"""
        if not self.collection:
            return

        try:
            await self.collection.update_one(
                {"type": "message", "message_id": message_id, "chat_id": chat_id},
                {"$set": {"file_path": file_path}},
            )
        except Exception as e:
            logger.error(f"Error updating message file path: {e}")

    async def _get_cached_messages(self, chat_id: int, limit: int) -> List[MessageModel]:
        """Get cached messages for a chat"""
        if not self.collection:
            return []

        try:
            cursor = (
                self.collection.find({"type": "message", "chat_id": chat_id})
                .sort("date", -1)
                .limit(limit)
            )

            messages = []
            async for doc in cursor:
                # Remove the "type" field added for cache
                if "type" in doc:
                    doc.pop("type")
                if "message_id" in doc:
                    doc.pop("message_id")

                messages.append(MessageModel(**doc))

            return messages

        except Exception as e:
            logger.error(f"Error getting cached messages: {e}")
            return []

    async def _find_chats_in_cache(self, query: str, limit: int) -> List[ChatModel]:
        """Find chats in cache by title or username"""
        if not self.collection:
            return []

        try:
            cursor = self.collection.find(
                {
                    "type": "chat",
                    "$or": [
                        {"title": {"$regex": query, "$options": "i"}},
                        {"username": {"$regex": query, "$options": "i"}},
                    ],
                }
            ).limit(limit)

            chats = []
            async for doc in cursor:
                # Remove the "type" field added for cache
                if "type" in doc:
                    doc.pop("type")
                if "chat_id" in doc:
                    doc.pop("chat_id")

                chats.append(ChatModel(**doc))

            return chats

        except Exception as e:
            logger.error(f"Error finding chats in cache: {e}")
            return []

    async def _find_messages_in_cache(
        self, query: str, chat_id: int, limit: int
    ) -> List[MessageModel]:
        """Find messages in cache by text content"""
        if not self.collection:
            return []

        try:
            cursor = self.collection.find(
                {"type": "message", "chat_id": chat_id, "text": {"$regex": query, "$options": "i"}}
            ).limit(limit)

            messages = []
            async for doc in cursor:
                # Remove the "type" field added for cache
                if "type" in doc:
                    doc.pop("type")
                if "message_id" in doc:
                    doc.pop("message_id")

                messages.append(MessageModel(**doc))

            return messages

        except Exception as e:
            logger.error(f"Error finding messages in cache: {e}")
            return []


def setup_dispatcher(dp: Dispatcher) -> Dispatcher:
    """Setup dispatcher with ChatFetcher commands"""
    from aiogram.filters import Command
    from aiogram.types import Message

    from botspot.commands_menu import add_command
    from botspot.utils.deps_getters import get_chat_fetcher

    @add_command("list_chats", "List your Telegram chats", visibility="hidden")
    @dp.message(Command("list_chats"))
    async def list_chats_command(message: Message) -> None:
        try:
            chat_fetcher = get_chat_fetcher()
            chats = await chat_fetcher.get_chats(message.from_user.id, limit=10)

            if not chats:
                await message.reply("No chats found.")
                return

            result = "Your recent chats:\n\n"
            for chat in chats:
                username = f" (@{chat.username})" if chat.username else ""
                result += f"• {chat.title}{username} [{chat.type}]\n"

            await message.reply(result)
        except Exception as e:
            logger.error(f"Error in list_chats_command: {e}")
            await message.reply(f"Error listing chats: {str(e)}")

    @add_command("search_chat", "Search for a chat by name", visibility="hidden")
    @dp.message(Command("search_chat"))
    async def search_chat_command(message: Message) -> None:
        try:
            parts = message.text.split(maxsplit=1)
            if len(parts) < 2:
                await message.reply("Please provide a search query, e.g. /search_chat Python")
                return

            query = parts[1]

            chat_fetcher = get_chat_fetcher()
            chats = await chat_fetcher.find_chat(query, message.from_user.id)

            if not chats:
                await message.reply(f"No chats found matching '{query}'.")
                return

            result = f"Chats matching '{query}':\n\n"
            for chat in chats:
                username = f" (@{chat.username})" if chat.username else ""
                result += f"• {chat.title}{username} [{chat.type}]\n"

            await message.reply(result)
        except Exception as e:
            logger.error(f"Error in search_chat_command: {e}")
            await message.reply(f"Error searching chats: {str(e)}")

    return dp


def initialize(settings: ChatFetcherSettings) -> ChatFetcher:
    """Initialize ChatFetcher component"""
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()

    # Get MongoDB collection if available
    collection = None
    if settings.cache_enabled and deps.botspot_settings.mongo_database.enabled:
        try:
            collection = deps.mongo_database[settings.collection_name]
            logger.info(f"ChatFetcher using MongoDB collection: {settings.collection_name}")
        except Exception as e:
            logger.error(f"Error getting MongoDB collection: {e}")

    # Get single user mode settings if enabled
    single_user_id = None
    if deps.botspot_settings.single_user_mode.enabled:
        single_user_id = deps.botspot_settings.single_user_mode.user

    return ChatFetcher(settings, collection, single_user_id)


def get_chat_fetcher() -> ChatFetcher:
    """Get ChatFetcher instance from dependency manager"""
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    return deps.chat_fetcher
