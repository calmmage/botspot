from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from aiogram import Dispatcher
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from telegram_downloader.config import StorageMode
from telegram_downloader.data_model import ChatData
from telegram_downloader.telegram_downloader import TelegramDownloader

from botspot.utils.internal import get_logger

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorCollection  # noqa: F401
    from telethon import TelegramClient
    from telethon.types import Message

logger = get_logger()


class ChatFetcherSettings(BaseSettings):
    enabled: bool = False
    cache_enabled: bool = True
    collection_name: str = "telegram_messages"
    chats_collection_name: str = "telegram_chats"
    max_messages_per_request: int = 100
    storage_mode: str = "mongo"
    recent_threshold_days: int = 30

    # Chat download limits
    backdays: Optional[int] = 30  # How far back to download messages (days)
    limit: Optional[int] = 1000  # Maximum number of messages to download per chat
    skip_big: bool = True  # Skip chats with many participants

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
    finished_downloading: bool = False

    @classmethod
    def from_chat_data(cls, chat_data: ChatData) -> "ChatModel":
        """Convert ChatData from telegram-downloader to ChatModel"""
        chat_type = chat_data.entity_category

        # Get username if available
        username = None
        if hasattr(chat_data.entity, "username"):
            username = chat_data.entity.username

        # Get title or generate from name
        if hasattr(chat_data.entity, "title"):
            title = chat_data.entity.title
        else:
            # For users, create title from first/last name
            name_parts = []
            if hasattr(chat_data.entity, "first_name") and chat_data.entity.first_name:
                name_parts.append(chat_data.entity.first_name)
            if hasattr(chat_data.entity, "last_name") and chat_data.entity.last_name:
                name_parts.append(chat_data.entity.last_name)
            title = " ".join(name_parts) if name_parts else f"Chat {chat_data.id}"

        return cls(
            id=chat_data.id,
            title=title,
            username=username,
            type=chat_type,
            last_message_date=chat_data.last_message_date,
            finished_downloading=chat_data.finished_downloading,
        )


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

    @classmethod
    def from_telethon_message(cls, message: "Message", chat_id: int) -> "MessageModel":
        """Convert Telethon message to MessageModel"""
        # Determine media type
        media_type = None
        has_media = False

        if hasattr(message, "media") and message.media:
            has_media = True
            media_type = type(message.media).__name__

        return cls(
            id=message.id,
            chat_id=chat_id,
            text=message.text if hasattr(message, "text") else None,
            date=message.date,
            from_id=(
                message.from_id.user_id if hasattr(message, "from_id") and message.from_id else None
            ),
            reply_to_message_id=(
                message.reply_to.reply_to_msg_id
                if hasattr(message, "reply_to") and message.reply_to
                else None
            ),
            media=has_media,
            media_type=media_type,
        )


class ChatFetcher:
    """Component for fetching and caching Telegram chats and messages using telegram-downloader"""

    def __init__(
        self,
        settings: ChatFetcherSettings,
        messages_collection: Optional["AsyncIOMotorCollection"] = None,
        chats_collection: Optional["AsyncIOMotorCollection"] = None,
        single_user_id: Optional[str] = None,
    ):
        self.settings = settings
        self.messages_collection = messages_collection
        self.chats_collection = chats_collection
        self.single_user_id = single_user_id
        self._telegram_downloader = None
        self._telethon_client = None
        logger.info(f"ChatFetcher initialized with cache_enabled={settings.cache_enabled}")

    @property
    def storage_mode(self) -> StorageMode:
        """Get storage mode (mongo or local)"""
        if self.settings.storage_mode.lower() == "mongo":
            return StorageMode.MONGO
        else:
            return StorageMode.LOCAL

    async def get_telegram_downloader(self, user_id: Optional[int] = None) -> TelegramDownloader:
        """Get or create TelegramDownloader instance"""
        if self._telegram_downloader is not None:
            return self._telegram_downloader

        # Resolve user_id
        resolved_user_id = await self._resolve_user_id(user_id)

        # Configure environment for TelegramDownloader
        from botspot.core.dependency_manager import get_dependency_manager

        deps = get_dependency_manager()
        telegram_settings = deps.botspot_settings.telethon_manager
        mongo_settings = deps.botspot_settings.mongo_database

        # Create config for TelegramDownloader
        config = {
            "storage_mode": self.storage_mode.value,
            "TELEGRAM_API_ID": telegram_settings.api_id,
            "TELEGRAM_API_HASH": telegram_settings.api_hash,
            "TELEGRAM_USER_ID": str(resolved_user_id),
        }

        if self.storage_mode == StorageMode.MONGO and mongo_settings.enabled:
            config.update(
                {
                    "MONGO_CONN_STR": mongo_settings.mongo_uri,
                    "MONGO_DB_NAME": mongo_settings.db_name,
                    "MONGO_MESSAGES_COLLECTION": self.settings.collection_name,
                    "MONGO_CHATS_COLLECTION": self.settings.chats_collection_name,
                }
            )

        # Create downloader
        self._telegram_downloader = TelegramDownloader(**config)
        return self._telegram_downloader

    async def get_client(self, user_id: Optional[int] = None) -> "TelegramClient":
        """Get telethon client for the specified user or for single user mode"""
        if self._telethon_client is not None:
            return self._telethon_client

        # Try to get client from TelegramDownloader
        try:
            downloader = await self.get_telegram_downloader(user_id)
            self._telethon_client = await downloader.get_telethon_client()
            return self._telethon_client
        except Exception as e:
            logger.error(f"Error getting client from TelegramDownloader: {e}")

        # Fallback to telethon_manager
        from botspot.components.main.telethon_manager import get_telethon_manager

        telethon_manager = get_telethon_manager()
        resolved_user_id = await self._resolve_user_id(user_id)
        self._telethon_client = await telethon_manager.get_client(resolved_user_id)
        return self._telethon_client

    async def _resolve_user_id(self, user_id: Optional[int] = None) -> int:
        """Resolve user_id, using single user mode if needed"""
        if user_id is not None:
            return user_id

        from botspot.core.dependency_manager import get_dependency_manager

        deps = get_dependency_manager()
        if not deps.botspot_settings.single_user_mode.enabled:
            raise ValueError("User ID must be provided when not in single user mode")

        user = deps.botspot_settings.single_user_mode.user
        # Convert username to numeric ID if needed
        if user.startswith("@"):
            # TODO: Implement username to ID conversion
            raise NotImplementedError("Username conversion not implemented yet")
        return int(user)

    async def get_chats(self, user_id: Optional[int] = None, limit: int = 100) -> List[ChatModel]:
        """Get chats for the specified user or for single user mode using telegram-downloader"""
        downloader = await self.get_telegram_downloader(user_id)

        # Use telegram-downloader to get chats
        chat_data_list = await downloader._get_chats()

        # Limit the number of chats if needed
        if limit:
            chat_data_list = chat_data_list[:limit]

        # Convert to ChatModel
        chats = [ChatModel.from_chat_data(chat) for chat in chat_data_list]

        return chats

    async def find_chat(
        self, query: str, user_id: Optional[int] = None, limit: int = 5
    ) -> List[ChatModel]:
        """Find chats by title or username"""
        downloader = await self.get_telegram_downloader(user_id)

        # Try to find chats using telegram-downloader's built-in functions
        try:
            # Get all chats and filter locally
            chats_data = await downloader._get_chats()

            # Filter chats by query in name
            query = query.lower()
            filtered_chats = []

            for chat in chats_data:
                chat_name = chat.name.lower()
                if query in chat_name:
                    filtered_chats.append(chat)

            # Convert to ChatModel and limit
            return [ChatModel.from_chat_data(chat) for chat in filtered_chats[:limit]]

        except Exception as e:
            logger.error(f"Error finding chats in telegram-downloader: {e}")

            # Fallback to original cache method
            if self.settings.cache_enabled and self.messages_collection:
                cached_chats = await self._find_chats_in_cache(query, limit)
                if cached_chats:
                    return cached_chats

        # If all else fails, get all chats and filter manually
        chats = await self.get_chats(user_id, limit=100)

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
        """Get messages from a specific chat using telegram-downloader"""
        downloader = await self.get_telegram_downloader(user_id)

        # Get chat entity
        chats = await downloader._get_chats()
        chat_data = next((chat for chat in chats if chat.id == chat_id), None)

        if not chat_data:
            logger.error(f"Chat with ID {chat_id} not found")
            return []

        # Use telegram-downloader to load messages
        kwargs = {"limit": min(limit, self.settings.max_messages_per_request)}

        if offset_id:
            kwargs["offset_id"] = offset_id

        if min_id:
            kwargs["min_id"] = min_id

        if max_id:
            kwargs["max_id"] = max_id

        if reverse:
            kwargs["reverse"] = reverse

        try:
            messages = await downloader._load_messages(chat_data, **kwargs)

            # Convert to MessageModel
            result = []
            for msg in messages:
                message = MessageModel.from_telethon_message(msg, chat_id)
                result.append(message)

            return result

        except Exception as e:
            logger.error(f"Error loading messages with telegram-downloader: {e}")

            # Fallback to direct Telethon access
            client = await self.get_client(user_id)

            # Try to get from cache first if appropriate
            if (
                self.settings.cache_enabled
                and self.messages_collection
                and not min_id
                and not max_id
                and offset_id == 0
            ):
                cached_messages = await self._get_cached_messages(chat_id, limit)
                if cached_messages:
                    return cached_messages

            # Get messages from Telethon
            messages = await client.get_messages(
                chat_id,
                limit=limit,
                offset_id=offset_id,
                min_id=min_id,
                max_id=max_id,
                reverse=reverse,
            )
            assert messages is not None

            # Convert to MessageModel
            result = []
            for msg in messages:
                message = MessageModel.from_telethon_message(msg, chat_id)
                result.append(message)

                # Cache the message
                if self.settings.cache_enabled and self.messages_collection:
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
        if search_in_cached and self.settings.cache_enabled and self.messages_collection:
            cached_messages = await self._find_messages_in_cache(query, chat_id, limit)
            if cached_messages:
                return cached_messages

        # If not found in cache, use telethon's search function
        client = await self.get_client(user_id)
        messages = await client.get_messages(chat_id, search=query, limit=limit)
        assert messages is not None

        # Convert to MessageModel
        result = []
        for msg in messages:
            message = MessageModel.from_telethon_message(msg, chat_id)
            result.append(message)

            # Cache the message if caching is enabled
            if self.settings.cache_enabled and self.messages_collection:
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
        if self.settings.cache_enabled and self.messages_collection and file_path:
            await self._update_message_file_path(message_id, chat_id, str(file_path))

        return str(file_path) if file_path else None

    async def load_chat_history(
        self,
        chat_id: int,
        user_id: Optional[int] = None,
        backdays: Optional[int] = None,
        limit: Optional[int] = None,
        ignore_finished: bool = False,
    ) -> List[MessageModel]:
        """
        Load full chat history using telegram-downloader's advanced features

        This method uses telegram-downloader to efficiently download all messages from a chat,
        with support for incremental updates, pagination, and rate limiting.

        Args:
            chat_id: ID of the chat to download messages from
            user_id: User ID to use for authentication (optional if single_user_mode is enabled)
            backdays: Number of days to look back (default from settings)
            limit: Maximum messages to download (default from settings)
            ignore_finished: Whether to ignore the "finished_downloading" flag

        Returns:
            List of downloaded messages as MessageModel objects
        """
        downloader = await self.get_telegram_downloader(user_id)

        # Get chat entity
        chats = await downloader._get_chats()
        chat_data = next((chat for chat in chats if chat.id == chat_id), None)

        if not chat_data:
            logger.error(f"Chat with ID {chat_id} not found")
            return []

        # Configure download limits
        from telegram_downloader.config import ChatCategoryConfig

        chat_config = ChatCategoryConfig(
            enabled=True,
            backdays=backdays or self.settings.backdays,
            limit=limit or self.settings.limit,
            skip_big=self.settings.skip_big,
        )

        # Download messages
        raw_messages = await downloader._download_messages(
            chat_data, chat_config, ignore_finished=ignore_finished
        )

        # Convert to MessageModel
        result = []
        for msg in raw_messages:
            try:
                message = MessageModel.from_telethon_message(msg, chat_id)
                result.append(message)
            except Exception as e:
                logger.error(f"Error converting message {msg.id}: {e}")

        return result

    # Cache-related methods
    async def _cache_chat(self, chat: ChatModel) -> None:
        """Cache chat information"""
        if not self.chats_collection:
            return

        try:
            # Use dict() to convert to dictionary
            chat_dict = chat.dict()

            # Upsert the chat
            await self.chats_collection.update_one(
                {"id": chat.id}, {"$set": chat_dict}, upsert=True
            )

        except Exception as e:
            logger.error(f"Error caching chat: {e}")

    async def _cache_message(self, message: MessageModel) -> None:
        """Cache message information"""
        if not self.messages_collection:
            return

        try:
            # Convert to dict and add metadata for easier querying
            msg_dict = message.dict()

            # Upsert the message
            await self.messages_collection.update_one(
                {"id": message.id, "chat_id": message.chat_id}, {"$set": msg_dict}, upsert=True
            )

        except Exception as e:
            logger.error(f"Error caching message: {e}")

    async def _update_message_file_path(
        self, message_id: int, chat_id: int, file_path: str
    ) -> None:
        """Update file path in cached message"""
        if not self.messages_collection:
            return

        try:
            await self.messages_collection.update_one(
                {"id": message_id, "chat_id": chat_id},
                {"$set": {"file_path": file_path}},
            )
        except Exception as e:
            logger.error(f"Error updating message file path: {e}")

    async def _get_cached_messages(self, chat_id: int, limit: int) -> List[MessageModel]:
        """Get cached messages for a chat"""
        if not self.messages_collection:
            return []

        try:
            cursor = (
                self.messages_collection.find({"chat_id": chat_id}).sort("date", -1).limit(limit)
            )

            messages = []
            async for doc in cursor:
                # Remove the MongoDB _id field
                if "_id" in doc:
                    doc.pop("_id")

                messages.append(MessageModel(**doc))

            return messages

        except Exception as e:
            logger.error(f"Error getting cached messages: {e}")
            return []

    async def _find_chats_in_cache(self, query: str, limit: int) -> List[ChatModel]:
        """Find chats in cache by title or username"""
        if not self.chats_collection:
            return []

        try:
            cursor = self.chats_collection.find(
                {
                    "$or": [
                        {"title": {"$regex": query, "$options": "i"}},
                        {"username": {"$regex": query, "$options": "i"}},
                    ],
                }
            ).limit(limit)

            chats = []
            async for doc in cursor:
                # Remove the MongoDB _id field
                if "_id" in doc:
                    doc.pop("_id")

                chats.append(ChatModel(**doc))

            return chats

        except Exception as e:
            logger.error(f"Error finding chats in cache: {e}")
            return []

    async def _find_messages_in_cache(
        self, query: str, chat_id: int, limit: int
    ) -> List[MessageModel]:
        """Find messages in cache by text content"""
        if not self.messages_collection:
            return []

        try:
            cursor = self.messages_collection.find(
                {"chat_id": chat_id, "text": {"$regex": query, "$options": "i"}}
            ).limit(limit)

            messages = []
            async for doc in cursor:
                # Remove the MongoDB _id field
                if "_id" in doc:
                    doc.pop("_id")

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

    @add_command("download_chat", "Download all messages from a chat", visibility="hidden")
    @dp.message(Command("download_chat"))
    async def download_chat_command(message: Message) -> None:
        try:
            parts = message.text.split(maxsplit=2)
            if len(parts) < 2:
                await message.reply(
                    "Please provide a chat ID or search query, e.g. /download_chat 123456789 or /download_chat Python Group"
                )
                return

            chat_fetcher = get_chat_fetcher()

            # Try to parse chat_id directly
            try:
                chat_id = int(parts[1])
                chat_name = str(chat_id)
                limit = int(parts[2]) if len(parts) > 2 else None
            except ValueError:
                # If not an ID, treat as a search query
                query = parts[1]
                chats = await chat_fetcher.find_chat(query, message.from_user.id, limit=1)
                if not chats:
                    await message.reply(f"No chats found matching '{query}'.")
                    return
                chat_id = chats[0].id
                chat_name = chats[0].title
                limit = int(parts[2]) if len(parts) > 2 else None

            # Send initial response
            status_message = await message.reply(
                f"Starting download of messages from '{chat_name}'..."
            )

            # Use the load_chat_history method from telegram-downloader
            messages = await chat_fetcher.load_chat_history(
                chat_id=chat_id, user_id=message.from_user.id, limit=limit
            )

            # Send completion message
            if messages:
                await status_message.edit_text(
                    f"Successfully downloaded {len(messages)} messages from '{chat_name}'.\n\n"
                    f"Date range: {min(msg.date for msg in messages).strftime('%d %b %Y')} - "
                    f"{max(msg.date for msg in messages).strftime('%d %b %Y')}"
                )
            else:
                await status_message.edit_text(
                    f"No messages found in '{chat_name}' or download was skipped."
                )

        except Exception as e:
            logger.error(f"Error in download_chat_command: {e}")
            await message.reply(f"Error downloading chat: {str(e)}")

    return dp


def initialize(settings: ChatFetcherSettings) -> ChatFetcher:
    """Initialize ChatFetcher component"""
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()

    # Get MongoDB collections if available
    messages_collection = None
    chats_collection = None
    if settings.cache_enabled and deps.botspot_settings.mongo_database.enabled:
        try:
            messages_collection = deps.mongo_database[settings.collection_name]
            chats_collection = deps.mongo_database[settings.chats_collection_name]
            logger.info(
                f"ChatFetcher using MongoDB collections: {settings.collection_name} and {settings.chats_collection_name}"
            )
        except Exception as e:
            logger.error(f"Error getting MongoDB collections: {e}")

    # Get single user mode settings if enabled
    single_user_id = None
    if deps.botspot_settings.single_user_mode.enabled:
        single_user_id = deps.botspot_settings.single_user_mode.user

    return ChatFetcher(settings, messages_collection, chats_collection, single_user_id)


def get_chat_fetcher() -> ChatFetcher:
    """Get ChatFetcher instance from dependency manager"""
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    return deps.chat_fetcher
