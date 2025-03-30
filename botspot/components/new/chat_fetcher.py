from typing import Dict, List, Optional, Union

from pydantic_settings import BaseSettings
from telethon import TelegramClient
from telethon.types import Channel, Chat, Dialog, Message, User

from botspot.core.errors import BotspotError


class ChatFetcherSettings(BaseSettings):
    enabled: bool = False
    db_cache_enabled: bool = False  # Switch for future DB caching
    default_dialogs_limit: Optional[int] = None

    class Config:
        env_prefix = "BOTSPOT_CHAT_FETCHER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class GetChatsResponse:
    users: List[User] = []
    channels: List[Channel] = []
    groups: List[Union[Chat, Channel]] = []


class ChatFetcher:
    def __init__(self, settings: ChatFetcherSettings):
        self.settings = settings
        self.clients: Dict[int, TelegramClient] = {}
        self._dialogs: Dict[int, List[Dialog]] = {}
        # In-memory cache for messages: (user_id, chat_id) -> List[Message]
        self._message_cache: Dict[tuple[int, int], List[Message]] = {}
        from botspot.core.dependency_manager import get_dependency_manager

        deps = get_dependency_manager()
        self.single_user_mode = deps.botspot_settings.single_user_mode.enabled
        self.single_user = deps.botspot_settings.single_user_mode.user

        if settings.db_cache_enabled:
            raise BotspotError(
                "DB caching is not implemented yet.",
                user_message="Please disable db caching in chat_fetcher - it's not implemented",
            )

    async def _get_client(self, user_id: Optional[int] = None) -> TelegramClient:
        if self.single_user_mode:
            if user_id is not None and str(user_id) != self.single_user:
                raise ValueError("Single user mode is enabled. Cannot use different user_id.")
            user_id = int(self.single_user) if self.single_user else None

        if user_id is None:
            raise ValueError("user_id is required")

        if user_id not in self.clients:
            from botspot import get_telethon_client

            self.clients[user_id] = await get_telethon_client(user_id)
        return self.clients[user_id]

    async def get_dialogs(self, user_id: int) -> List[Dialog]:
        if user_id not in self._dialogs:
            self._dialogs[user_id] = await self._get_dialogs(user_id)
        return self._dialogs[user_id]

    async def _get_dialogs(self, user_id: int) -> List[Dialog]:
        client = await self._get_client(user_id)
        return await client.get_dialogs()

    async def _get_chat(self, chat_id: int, user_id: int) -> Chat:
        client = await self._get_client(user_id)
        entity = await client.get_entity(chat_id)
        if isinstance(entity, Chat):
            return entity
        else:
            from botspot.core.errors import BotspotError

            raise BotspotError(
                f"Entity {entity} is not a Chat",
                user_message="Chat Fetcher is still experimental, please contact the botspot team about this issue",
            )

    async def _get_old_messages(
        self, chat_id: int, user_id: int, timestamp: int, limit: Optional[int] = None
    ) -> List[Message]:
        """Get chat messages older than timestamp."""
        client = await self._get_client(user_id)
        messages = await client.get_messages(chat_id, offset_date=timestamp, limit=limit)
        if isinstance(messages, Message):
            return [messages]
        else:
            return list(messages) if messages is not None else []

    async def _get_new_messages(
        self, chat_id: int, user_id: int, timestamp: int, limit: Optional[int] = None
    ) -> List[Message]:
        """Get chat messages newer than timestamp."""
        client = await self._get_client(user_id)
        messages = await client.get_messages(
            chat_id, offset_date=timestamp, limit=limit, reverse=True
        )
        if isinstance(messages, Message):
            return [messages]
        else:
            return list(messages) if messages is not None else []

    # endregion

    # region 2: cached methods

    # endregion

    async def get_chat_messages(
        self, chat_id: int, user_id: Optional[int] = None, limit: int = 100
    ) -> List[Message]:
        """
        Get the most recent messages from a chat, using an in-memory cache when possible.

        Args:
            chat_id: The ID of the chat.
            user_id: The ID of the user (required unless in single-user mode).
            limit: Number of messages to return (default 100).

        Returns:
            List of Message objects, most recent first.
        """
        client = await self._get_client(user_id)
        cache_key = (user_id, chat_id)

        # Check if cache exists and has enough messages
        if cache_key in self._message_cache:
            cached_messages = self._message_cache[cache_key]
            if len(cached_messages) >= limit:
                # Return the most recent 'limit' messages from cache
                return cached_messages[:limit]

        # Cache miss or insufficient messages: fetch from Telegram
        messages = await client.get_messages(chat_id, limit=limit)
        if isinstance(messages, Message):
            messages_list = [messages]
        else:
            messages_list = list(messages) if messages is not None else []

        # Update the cache with the fetched messages
        self._message_cache[cache_key] = messages_list

        # Return the requested number of messages
        return messages_list[:limit]

    async def get_chats(self, user_id: int, limit: Optional[int] = None) -> GetChatsResponse:
        client = await self._get_client(user_id)
        dialogs = await client.get_dialogs(limit=limit)
        response = GetChatsResponse()
        for dialog in dialogs:
            if isinstance(dialog.entity, User):
                response.users.append(dialog.entity)
            elif isinstance(dialog.entity, Chat):
                response.groups.append(dialog.entity)
            elif isinstance(dialog.entity, Channel):
                if dialog.entity.megagroup:
                    response.groups.append(dialog.entity)
                else:
                    response.channels.append(dialog.entity)
        return response

    async def search_chat(self, query: str, user_id: int) -> List[Chat]:
        client = await self._get_client(user_id)
        dialogs = await client.get_dialogs()
        results = []
        for dialog in dialogs:
            if query.lower() in dialog.name.lower():
                results.append(dialog.entity)
        return results

    # todo: rework to a better, embedding-based search with llm features
    async def search_message(
        self, query: str, user_id: int, chat_id: Optional[int] = None
    ) -> List[Message]:
        client = await self._get_client(user_id)
        if chat_id:
            return [msg async for msg in client.iter_messages(chat_id, search=query)]
        else:
            results = []
            dialogs = await client.get_dialogs()
            for dialog in dialogs:
                messages = [msg async for msg in client.iter_messages(dialog.id, search=query)]
                results.extend(messages)
            return results


def setup_dispatcher(dp):
    return dp


def initialize(settings: ChatFetcherSettings) -> ChatFetcher:
    cf = ChatFetcher(settings)
    return cf


def get_chat_fetcher() -> ChatFetcher:
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    return deps.chat_fetcher


if __name__ == "__main__":
    import asyncio

    from aiogram.types import Message

    async def fetch_messages(message: Message):
        user_id = message.from_user.id
        chat_id = -100123456789  # Replace with a real group chat ID

        # Get chat fetcher and retrieve messages
        fetcher = get_chat_fetcher()
        messages = await fetcher.get_chat_messages(chat_id, user_id, limit=10)

        # Print message text from retrieved messages
        for msg in messages:
            print(f"Message from {msg.sender_id}: {msg.text}")

    # Mock message for example
    asyncio.run(fetch_messages(Message(from_user={"id": 12345})))
