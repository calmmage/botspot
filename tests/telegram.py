"""In-process Telegram test client: a real aiogram Bot + Dispatcher, no network.

Outgoing Bot API methods are captured by a fake session. Feature tests feed
Updates through the dispatcher the same way polling would.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from aiogram import Bot, Dispatcher, Router
from aiogram.client.session.base import BaseSession
from aiogram.methods import TelegramMethod
from aiogram.methods.base import TelegramType
from aiogram.types import Chat, Message, MessageId, Update, User

from botspot.core.bot_manager import BotManager
from botspot.utils.internal import Singleton

TEST_TOKEN = "123456789:AATestingTokenForBotspotNotReal"
BOT_USER = User(id=123456789, is_bot=True, first_name="Botspot", username="botspot_test_bot")
DEFAULT_USER_ID = 1001
DEFAULT_CHAT_ID = 1001


class MockedSession(BaseSession):
    """Records every Bot API call and returns plausible Telegram objects."""

    def __init__(self) -> None:
        super().__init__()
        self.requests: list[TelegramMethod[Any]] = []
        self._n = 0
        self.closed = False
        self.failures: dict[str, Exception] = {}

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
        return self._result(method)  # type: ignore[return-value]

    def _result(self, method: TelegramMethod[Any]) -> Any:
        name = method.__api_method__
        if name == "getMe":
            return BOT_USER
        if name == "copyMessage":
            return MessageId(message_id=self._next_id())
        if name in {
            "setMyCommands",
            "deleteMessage",
            "answerCallbackQuery",
            "pinChatMessage",
            "unpinChatMessage",
        }:
            return True
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
) -> User:
    return User(id=user_id, is_bot=is_bot, first_name=first_name, username=username)


def make_message(
    text: str,
    *,
    user_id: int = DEFAULT_USER_ID,
    chat_id: int = DEFAULT_CHAT_ID,
    username: str = "tester",
    first_name: str = "Test",
    message_id: int = 1,
    **extra: Any,
) -> Message:
    user = make_user(user_id=user_id, username=username, first_name=first_name)
    data = dict(
        message_id=message_id,
        date=datetime.now(timezone.utc),
        chat=Chat(id=chat_id, type="private"),
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
        **botspot: Any,
    ) -> None:
        Singleton._instances = {}
        self.session = MockedSession()
        self.bot = Bot(token=TEST_TOKEN, session=self.session)
        self.dp = Dispatcher()
        for router in routers:
            self.dp.include_router(router)
        self.manager = BotManager(bot=self.bot, dispatcher=self.dp, **quiet_botspot(**botspot))
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

    async def send(
        self,
        text: str,
        *,
        user_id: int = DEFAULT_USER_ID,
        chat_id: int = DEFAULT_CHAT_ID,
        username: str = "tester",
        first_name: str = "Test",
        **extra: Any,
    ) -> list[TelegramMethod[Any]]:
        before = len(self.session.requests)
        async with self._ids:
            message_id = self._next_message()
            update_id = self._next_update()
        message = make_message(
            text,
            user_id=user_id,
            chat_id=chat_id,
            username=username,
            first_name=first_name,
            message_id=message_id,
            **extra,
        )
        await self.dp.feed_update(self.bot, make_update(message, update_id))
        return self.session.requests[before:]

    def texts(self, methods: Optional[Iterable[TelegramMethod[Any]]] = None) -> list[str]:
        return self.session.texts(methods)
