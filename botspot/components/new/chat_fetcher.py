from typing import Dict, List, Optional, Union

from pydantic_settings import BaseSettings
from telethon import TelegramClient
from telethon.types import Channel
from telethon.types import Chat
from telethon.types import Chat as GroupChat
from telethon.types import Dialog, Message, User


class ChatFetcherSettings(BaseSettings):
    enabled: bool = False
    db_cache_enabled: bool = False
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
        self.clients: Dict[int, TelegramClient] = {}
        self._dialogs: Dict[int, List[Dialog]] = {}
        from botspot.core.dependency_manager import get_dependency_manager

        deps = get_dependency_manager()
        self.single_user_mode = deps.botspot_settings.single_user_mode.enabled
        self.single_user = deps.botspot_settings.single_user_mode.user

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

    # region 1: uncached raw telethon methods
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
                user_message="Chat Fetcher is still expental, please contact the botspot team about this issue",
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
        client = await self._get_client(user_id)
        messages = await client.get_messages(chat_id, limit=limit)
        if isinstance(messages, Message):
            return [messages]
        else:
            return list(messages) if messages is not None else []

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
            # Search in all dialogs
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
