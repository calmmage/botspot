"""
Bind a chat to a user.

chat_binder(user_id: int, chat_id: int, key: Optional[str]=None)
get_bind_chat_id(user_id: int, key: Optional[str]=None) -> str

Feature 1: just bind chat to user as default
Feature 2: bind chat to user with key
"""

from typing import TYPE_CHECKING, List

from aiogram.filters import Command
from aiogram.types import Message
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorCollection  # noqa: F401

logger = get_logger()


class ChatBinderSettings(BaseSettings):
    enabled: bool = False
    mongo_collection: str = "chat_binder"
    commands_visible: bool = False

    class Config:
        env_prefix = "BOTSPOT_CHAT_BINDER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


def setup_dispatcher(dp):
    dp.message.register(bind_chat_command_handler, Command("bind_chat"))

    dp.message.register(unbind_chat_command_handler, Command("unbind_chat"))
    return dp


def initialize(settings: ChatBinderSettings) -> "AsyncIOMotorCollection":
    from botspot.core.dependency_manager import get_dependency_manager
    from botspot.utils.deps_getters import get_database

    # check that mongo db is available
    # todo: a more generic way to define required dependencies?
    deps = get_dependency_manager()
    if not deps.botspot_settings.mongo_database.enabled:
        raise RuntimeError("MongoDB is required for chat_binder component")

    from botspot.components.qol.bot_commands_menu import Visibility, add_command

    visibility = Visibility.PUBLIC if settings.commands_visible else Visibility.HIDDEN
    add_command("bind_chat", "Bind a chat to a user with provided key", visibility=visibility)(
        bind_chat_command_handler
    )
    add_command(
        "unbind_chat", "Unbind a chat from a user with provided key", visibility=visibility
    )(unbind_chat_command_handler)

    db = get_database()
    logger.info(f"Initializing chat_binder with collection {settings.mongo_collection}")
    return db.get_collection(settings.mongo_collection)


class BoundChatRecord(BaseModel):
    user_id: int
    chat_id: int
    key: str = "default"


async def bind_chat(user_id: int, chat_id: int, key: str = "default"):
    collection = get_bind_chat_collection()
    record = BoundChatRecord(user_id=user_id, chat_id=chat_id, key=key)
    # todo: sanity check?
    await collection.insert_one(record.model_dump())
    return record


async def unbind_chat(user_id: int, chat_id: int, key: str = "default"):
    collection = get_bind_chat_collection()
    await collection.delete_one({"user_id": user_id, "chat_id": chat_id, "key": key})


async def get_bind_chat_id(user_id: int, key: str = "default") -> str:
    collection = get_bind_chat_collection()
    record = await collection.find_one({"user_id": user_id, "key": key})
    if record is None:
        raise RuntimeError(f"No bind chat found for user {user_id} and key {key}")
    return record["chat_id"]


def get_bind_chat_collection() -> "AsyncIOMotorCollection":
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    return deps.chat_binder


async def bind_chat_command_handler(message: Message):
    # todo: handle edge cases - already bound
    chat_id = message.chat.id
    if message.from_user is None:
        raise RuntimeError("message.from_user is None")
    user_id = message.from_user.id
    if message.text is None:
        raise RuntimeError("message.text is None")
    key = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else "default"
    await bind_chat(user_id, chat_id, key)
    await message.reply("Chat bound successfully with key: " + key)


async def unbind_chat_command_handler(message: Message):
    # todo: handle edge cases - missing or multiple items found
    chat_id = message.chat.id
    if message.from_user is None:
        raise RuntimeError("message.from_user is None")
    user_id = message.from_user.id
    if message.text is None:
        raise RuntimeError("message.text is None")
    key = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else "default"
    await unbind_chat(user_id, chat_id, key)


async def get_user_bound_chats(user_id: int) -> List[BoundChatRecord]:
    collection = get_bind_chat_collection()
    records = await collection.find({"user_id": user_id}).to_list(length=100)
    return [BoundChatRecord(**record) for record in records]
