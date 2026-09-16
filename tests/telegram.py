"""In-process Telegram test client: a real aiogram Bot + Dispatcher, no network.

Outgoing Bot API methods are captured by a fake session. Feature tests feed
Updates through the dispatcher the same way polling would.

Mongo-backed components (chat_binder, queue_manager, access_control, auto_archive)
use MemoryDatabase — an in-process stand-in for AsyncMongoClient/Database/Collection.
"""

from __future__ import annotations

import asyncio
import copy
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Iterable, Optional

from aiogram import Bot, Dispatcher, Router
from aiogram.client.session.base import BaseSession
from aiogram.methods import TelegramMethod
from aiogram.methods.base import TelegramType
from aiogram.types import (
    CallbackQuery,
    Chat,
    ChatMemberMember,
    ChatMemberOwner,
    Message,
    MessageId,
    Update,
    User,
)
from bson import ObjectId

from botspot.components.data import mongo_database as mongo_mod
from botspot.core.bot_manager import BotManager
from botspot.utils.internal import Singleton

TEST_TOKEN = "123456789:AATestingTokenForBotspotNotReal"
BOT_USER = User(id=123456789, is_bot=True, first_name="Botspot", username="botspot_test_bot")
DEFAULT_USER_ID = 1001
DEFAULT_CHAT_ID = 1001

_BOOL_METHODS = {
    "setMyCommands",
    "deleteMessage",
    "answerCallbackQuery",
    "pinChatMessage",
    "unpinChatMessage",
    "sendChatAction",
}


class MemoryCursor:
    def __init__(self, docs: list[dict[str, Any]]):
        self._docs = docs

    def limit(self, n: Optional[int]) -> "MemoryCursor":
        if n is not None:
            self._docs = self._docs[:n]
        return self

    def sort(self, field: str, direction: int = 1) -> "MemoryCursor":
        reverse = direction < 0
        self._docs.sort(key=lambda d: d.get(field), reverse=reverse)
        return self

    async def to_list(self, length: Optional[int] = None) -> list[dict[str, Any]]:
        docs = self._docs if length is None else self._docs[:length]
        return [copy.deepcopy(d) for d in docs]

    def __aiter__(self) -> "MemoryCursor":
        self._iter = iter(self._docs)
        return self

    async def __anext__(self) -> dict[str, Any]:
        try:
            return copy.deepcopy(next(self._iter))
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class MemoryCollection:
    """Enough of pymongo's async Collection API for botspot components."""

    def __init__(self, name: str = "col") -> None:
        self.name = name
        self.docs: list[dict[str, Any]] = []

    def _matches(self, doc: dict[str, Any], filt: dict[str, Any]) -> bool:
        return all(doc.get(k) == v for k, v in filt.items())

    def _find_index(self, filt: dict[str, Any]) -> Optional[int]:
        for i, doc in enumerate(self.docs):
            if self._matches(doc, filt):
                return i
        return None

    def _project(self, doc: dict[str, Any], projection: Optional[dict[str, Any]]) -> dict[str, Any]:
        cloned = copy.deepcopy(doc)
        if not projection:
            return cloned
        if any(v for v in projection.values()):
            out: dict[str, Any] = {}
            if projection.get("_id", 1):
                if "_id" in cloned:
                    out["_id"] = cloned["_id"]
            for key, include in projection.items():
                if include and key in cloned:
                    out[key] = cloned[key]
            return out
        for key, include in projection.items():
            if not include:
                cloned.pop(key, None)
        return cloned

    async def find_one(
        self, filt: Optional[dict[str, Any]] = None, **_kwargs: Any
    ) -> Optional[dict[str, Any]]:
        filt = filt or {}
        for doc in self.docs:
            if self._matches(doc, filt):
                return copy.deepcopy(doc)
        return None

    def find(
        self,
        filt: Optional[dict[str, Any]] = None,
        projection: Optional[dict[str, Any]] = None,
        **_kwargs: Any,
    ) -> MemoryCursor:
        filt = filt or {}
        matched = [self._project(d, projection) for d in self.docs if self._matches(d, filt)]
        return MemoryCursor(matched)

    async def insert_one(self, doc: dict[str, Any]) -> SimpleNamespace:
        stored = copy.deepcopy(doc)
        if "_id" not in stored:
            stored["_id"] = ObjectId()
        self.docs.append(stored)
        return SimpleNamespace(inserted_id=stored["_id"])

    async def replace_one(
        self, filt: dict[str, Any], replacement: dict[str, Any], upsert: bool = False
    ) -> SimpleNamespace:
        idx = self._find_index(filt)
        stored = copy.deepcopy(replacement)
        if idx is None:
            if upsert:
                if "_id" not in stored:
                    stored["_id"] = ObjectId()
                self.docs.append(stored)
            return SimpleNamespace(matched_count=0, modified_count=0)
        if "_id" not in stored:
            stored["_id"] = self.docs[idx].get("_id")
        self.docs[idx] = stored
        return SimpleNamespace(matched_count=1, modified_count=1)

    async def delete_one(self, filt: dict[str, Any]) -> SimpleNamespace:
        idx = self._find_index(filt)
        if idx is None:
            return SimpleNamespace(deleted_count=0)
        self.docs.pop(idx)
        return SimpleNamespace(deleted_count=1)

    async def update_one(
        self, filt: dict[str, Any], update: dict[str, Any], upsert: bool = False
    ) -> SimpleNamespace:
        idx = self._find_index(filt)
        patch = update.get("$set", {})
        if idx is None:
            if not upsert:
                return SimpleNamespace(matched_count=0, modified_count=0, upserted_id=None)
            stored = {**copy.deepcopy(filt), **copy.deepcopy(patch)}
            if "_id" not in stored:
                stored["_id"] = ObjectId()
            self.docs.append(stored)
            return SimpleNamespace(matched_count=0, modified_count=0, upserted_id=stored["_id"])
        self.docs[idx].update(patch)
        return SimpleNamespace(matched_count=1, modified_count=1, upserted_id=None)


class MemoryDatabase:
    def __init__(self, name: str = "botspot_test") -> None:
        self.name = name
        self._cols: dict[str, MemoryCollection] = {}

    def get_collection(self, name: str) -> MemoryCollection:
        if name not in self._cols:
            self._cols[name] = MemoryCollection(name)
        return self._cols[name]

    def __getitem__(self, name: str) -> MemoryCollection:
        return self.get_collection(name)


class MemoryMongoClient:
    def __init__(self, database: MemoryDatabase) -> None:
        self._database = database

    def __getitem__(self, name: str) -> MemoryDatabase:
        return self._database

    async def close(self) -> None:
        return None


class MockedSession(BaseSession):
    """Records every Bot API call and returns plausible Telegram objects."""

    def __init__(self) -> None:
        super().__init__()
        self.requests: list[TelegramMethod[Any]] = []
        self._n = 0
        self.closed = False
        self.failures: dict[str, Exception] = {}
        self.chat_member_status: str = "creator"
        self.stream_body: bytes = b""

    def _next_id(self) -> int:
        self._n += 1
        return self._n

    def fail(self, api_method: str, exc: Exception) -> None:
        self.failures[api_method] = exc

    def by_method(self, api_method: str) -> list[TelegramMethod[Any]]:
        return [m for m in self.requests if m.__api_method__ == api_method]

    def texts(self, methods: Optional[Iterable[TelegramMethod[Any]]] = None) -> list[str]:
        out: list[str] = []
        for method in methods if methods is not None else self.requests:
            text = getattr(method, "text", None)
            if isinstance(text, str):
                out.append(text)
        return out

    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[TelegramType],
        timeout: int | None = None,
    ) -> TelegramType:
        self.requests.append(method)
        if method.__api_method__ in self.failures:
            raise self.failures[method.__api_method__]
        result = self._result(method)
        if isinstance(result, Message):
            result = result.as_(bot)
        return result  # type: ignore[return-value]

    def _result(self, method: TelegramMethod[Any]) -> Any:
        name = method.__api_method__
        if name == "getMe":
            return BOT_USER
        if name == "copyMessage":
            return MessageId(message_id=self._next_id())
        if name in _BOOL_METHODS:
            return True
        if name == "getChatMember":
            if self.chat_member_status in {"creator", "administrator"}:
                return ChatMemberOwner(user=BOT_USER, status="creator", is_anonymous=False)
            return ChatMemberMember(user=BOT_USER, status="member")
        chat_id = getattr(method, "chat_id", DEFAULT_CHAT_ID)
        try:
            cid = int(chat_id)
        except (TypeError, ValueError):
            cid = DEFAULT_CHAT_ID
        return Message(
            message_id=self._next_id(),
            date=datetime.now(timezone.utc),
            chat=Chat(id=cid, type="private"),
            from_user=BOT_USER,
            text=getattr(method, "text", None),
        )

    async def stream_content(
        self,
        url: str,
        headers: dict[str, Any] | None = None,
        timeout: int = 30,
        chunk_size: int = 65536,
        raise_for_status: bool = True,
    ) -> AsyncGenerator[bytes, None]:
        if self.stream_body:
            yield self.stream_body
            return
        if False:  # pragma: no cover - keep this an async generator
            yield b""
        return

    async def close(self) -> None:
        self.closed = True


def make_user(
    user_id: int = DEFAULT_USER_ID,
    username: str = "tester",
    first_name: str = "Test",
    is_bot: bool = False,
    language_code: Optional[str] = None,
    last_name: Optional[str] = None,
) -> User:
    return User(
        id=user_id,
        is_bot=is_bot,
        first_name=first_name,
        last_name=last_name,
        username=username,
        language_code=language_code,
    )


def make_chat(chat_id: int = DEFAULT_CHAT_ID, chat_type: str = "private", **extra: Any) -> Chat:
    data: dict[str, Any] = {"id": chat_id, "type": chat_type}
    if chat_type != "private":
        data["title"] = extra.pop("title", "Test Group")
    data.update(extra)
    return Chat(**data)


def make_message(
    text: str,
    *,
    user_id: int = DEFAULT_USER_ID,
    chat_id: int = DEFAULT_CHAT_ID,
    username: str = "tester",
    first_name: str = "Test",
    message_id: int = 1,
    chat_type: str = "private",
    language_code: Optional[str] = None,
    **extra: Any,
) -> Message:
    last_name = extra.pop("last_name", None)
    user = make_user(
        user_id=user_id,
        username=username,
        first_name=first_name,
        language_code=language_code,
        last_name=last_name,
    )
    data = dict(
        message_id=message_id,
        date=datetime.now(timezone.utc),
        chat=make_chat(chat_id, chat_type),
        from_user=user,
        text=text,
    )
    data.update(extra)
    return Message(**data)


def make_update(message: Message, update_id: int = 1) -> Update:
    return Update(update_id=update_id, message=message)


def quiet_botspot(**overrides: Any) -> dict[str, Any]:
    """Disable network-backed components; keep the QoL surface on."""
    cfg: dict[str, Any] = {
        "mongo_database": {"enabled": False},
        "postgres_database": {"enabled": False},
        "event_scheduler": {"enabled": False},
        "telethon_manager": {"enabled": False},
        "user_data": {"enabled": False},
        "single_user_mode": {"enabled": False},
        "access_control": {"enabled": False},
        "chat_binder": {"enabled": False},
        "llm_provider": {"enabled": False},
        "queue_manager": {"enabled": False},
        "message_aggregator": {"enabled": False},
        "chat_fetcher": {"enabled": False},
        "auto_archive": {"enabled": False},
        "s3_storage": {"enabled": False},
        "trial_mode": {"enabled": False},
        "ask_user": {"enabled": False},
        "error_handling": {"enabled": True, "easter_eggs": False, "developer_chat_id": 0},
        "bot_info": {"enabled": True, "show_detailed_settings": False},
        "bot_commands_menu": {"enabled": True},
        "print_bot_url": {"enabled": True},
        "i18n": {"enabled": True},
        "send_safe": {"enabled": True},
    }
    cfg.update(overrides)
    return cfg


class BotClient:
    """One isolated bot: real BotManager + dispatcher, mocked Telegram HTTP."""

    def __init__(
        self,
        *routers: Router,
        mongo: bool = False,
        **botspot: Any,
    ) -> None:
        Singleton._instances = {}
        self.session = MockedSession()
        self.bot = Bot(token=TEST_TOKEN, session=self.session)
        self.dp = Dispatcher()
        for router in routers:
            self.dp.include_router(router)
        self.mongo: Optional[MemoryDatabase] = None
        restore = None
        if mongo:
            self.mongo = MemoryDatabase()
            fake_client = MemoryMongoClient(self.mongo)
            botspot.setdefault("mongo_database", {"enabled": True})
            orig = mongo_mod.initialize
            mongo_mod.initialize = lambda _settings: (fake_client, self.mongo)
            restore = orig
        try:
            self.manager = BotManager(bot=self.bot, dispatcher=self.dp, **quiet_botspot(**botspot))
        finally:
            if restore is not None:
                mongo_mod.initialize = restore
        self.manager.setup_dispatcher(self.dp)
        self._update_id = 0
        self._message_id = 0
        self._ids = asyncio.Lock()

    def _next_update(self) -> int:
        self._update_id += 1
        return self._update_id

    def _next_message(self) -> int:
        self._message_id += 1
        return self._message_id

    async def emit_startup(self) -> list[TelegramMethod[Any]]:
        before = len(self.session.requests)
        await self.dp.startup.trigger(bot=self.bot)
        return self.session.requests[before:]

    async def emit_shutdown(self) -> list[TelegramMethod[Any]]:
        before = len(self.session.requests)
        await self.dp.shutdown.trigger(bot=self.bot)
        return self.session.requests[before:]

    async def send(
        self,
        text: str,
        *,
        user_id: int = DEFAULT_USER_ID,
        chat_id: int = DEFAULT_CHAT_ID,
        username: str = "tester",
        first_name: str = "Test",
        last_name: Optional[str] = None,
        chat_type: str = "private",
        language_code: Optional[str] = None,
        **extra: Any,
    ) -> list[TelegramMethod[Any]]:
        before = len(self.session.requests)
        async with self._ids:
            message_id = self._next_message()
            update_id = self._next_update()
        extra.setdefault("last_name", last_name)
        message = make_message(
            text,
            user_id=user_id,
            chat_id=chat_id,
            username=username,
            first_name=first_name,
            message_id=message_id,
            chat_type=chat_type,
            language_code=language_code,
            **extra,
        )
        await self.dp.feed_update(self.bot, make_update(message, update_id))
        return self.session.requests[before:]

    async def callback(
        self,
        data: str,
        *,
        user_id: int = DEFAULT_USER_ID,
        chat_id: int = DEFAULT_CHAT_ID,
        username: str = "tester",
        first_name: str = "Test",
        message_id: Optional[int] = None,
        message_text: str = "",
        language_code: Optional[str] = None,
    ) -> list[TelegramMethod[Any]]:
        before = len(self.session.requests)
        async with self._ids:
            update_id = self._next_update()
            if message_id is None:
                message_id = self._next_message()
        user = make_user(
            user_id=user_id,
            username=username,
            first_name=first_name,
            language_code=language_code,
        )
        message = Message(
            message_id=message_id,
            date=datetime.now(timezone.utc),
            chat=make_chat(chat_id),
            from_user=BOT_USER,
            text=message_text,
        )
        query = CallbackQuery(
            id=str(update_id),
            from_user=user,
            chat_instance="test",
            data=data,
            message=message,
        )
        await self.dp.feed_update(self.bot, Update(update_id=update_id, callback_query=query))
        return self.session.requests[before:]

    def texts(self, methods: Optional[Iterable[TelegramMethod[Any]]] = None) -> list[str]:
        return self.session.texts(methods)
