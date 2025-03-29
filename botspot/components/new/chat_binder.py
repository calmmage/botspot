"""
Bind a chat to a user.

chat_binder(user_id: int, chat_id: int, key: Optional[str]=None)
get_bind_chat_id(user_id: int, key: Optional[str]=None) -> str

Feature 1: just bind chat to user as default
Feature 2: bind chat to user with key
Feature 3: check if bot is admin in a chat
Feature 4: get users by chat ID
"""

from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Union

from aiogram.filters import Command
from aiogram.types import Message
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorCollection  # noqa: F401

logger = get_logger()


class RebindMode(str, Enum):
    """Defines how to handle rebinding a chat key."""

    REPLACE = "replace"  # Replace existing binding with new one
    ERROR = "error"  # Raise an error if key is already bound
    IGNORE = "ignore"  # Keep existing binding and ignore rebind attempt


class ChatBinderSettings(BaseSettings):
    enabled: bool = False
    mongo_collection: str = "chat_binder"
    commands_visible: bool = False
    rebind_mode: RebindMode = RebindMode.ERROR
    # Flag to check access status during binding
    check_access: bool = True

    class Config:
        env_prefix = "BOTSPOT_CHAT_BINDER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class BoundChatRecord(BaseModel):
    user_id: int
    chat_id: int
    key: str = "default"
    has_access: Optional[bool] = None  # Whether the bot has access via admin or chat_fetcher


class ChatBinder:
    def __init__(
        self, settings: ChatBinderSettings, collection: Optional["AsyncIOMotorCollection"] = None
    ):
        """Initialize the ChatBinder.

        Args:
            settings: Component settings
            collection: MongoDB collection for storing chat bindings
        """
        self.settings = settings
        if collection is None:
            from botspot.utils.deps_getters import get_database

            # Initialize database collection
            db = get_database()
            logger.info(f"Initializing chat_binder with collection {settings.mongo_collection}")
            collection = db.get_collection(settings.mongo_collection)
        self.collection = collection

        from botspot.core.dependency_manager import get_dependency_manager

        deps = get_dependency_manager()
        self.chat_fetcher_available = (
            hasattr(deps, "chat_fetcher") and deps.chat_fetcher is not None
        )

    async def bind_chat(self, user_id: int, chat_id: int, key: str = "default"):
        """Bind a chat to a user with the given key.

        Behavior depends on rebind_mode setting:
        - REPLACE: If the key is already bound, replace it with the new chat
        - ERROR: If the key is already bound, raise an error
        - IGNORE: If the key is already bound, do nothing and return existing record

        Additionally:
        - Checks if the bot has access to the chat (admin or chat_fetcher)
        """
        has_access = None

        # Check access status if enabled
        if self.settings.check_access:
            # First check if chat_fetcher component is available (preferred method)
            if self.chat_fetcher_available:
                has_access = True
            else:
                # Fallback to checking admin status
                has_access = await self.is_bot_admin(chat_id)

        # Check if this key is already bound
        existing = await self.collection.find_one({"user_id": user_id, "key": key})

        if existing:
            if self.settings.rebind_mode == RebindMode.ERROR:
                from botspot.core.errors import ChatBindingExistsError
                raise ChatBindingExistsError(f"Chat key '{key}' is already bound to chat {existing['chat_id']}")
            elif self.settings.rebind_mode == RebindMode.IGNORE:
                return BoundChatRecord(**existing)
            elif self.settings.rebind_mode == RebindMode.REPLACE:
                # Replace the existing binding
                record = BoundChatRecord(
                    user_id=user_id, chat_id=chat_id, key=key, has_access=has_access
                )
                await self.collection.replace_one(
                    {"user_id": user_id, "key": key}, record.model_dump()
                )
                return record
        else:
            # Create new binding
            record = BoundChatRecord(
                user_id=user_id, chat_id=chat_id, key=key, has_access=has_access
            )
            await self.collection.insert_one(record.model_dump())
            return record

    async def get_chat_binding_status(self, user_id: int, chat_id: int) -> List[BoundChatRecord]:
        """Get all bindings for a specific user and chat combination.

        Args:
            user_id: User ID to check
            chat_id: Chat ID to check

        Returns:
            List of BoundChatRecord objects representing all bindings for this chat
        """
        records = await self.collection.find({"user_id": user_id, "chat_id": chat_id}).to_list(
            length=100
        )
        return [BoundChatRecord(**record) for record in records]

    async def unbind_chat(
        self, user_id: int, key: str = "default", chat_id: Optional[int] = None
    ) -> Tuple[bool, str]:
        """Unbind a chat from a user with the given key.

        Args:
            user_id: User ID
            key: Binding key to remove

        Returns:
            True if a binding was removed, False otherwise

        Raises:
            ValueError: If no binding exists with the given key
        """
        # First check if the binding exists
        existing = await self.collection.find_one({"user_id": user_id, "key": key})

        # If no binding found with the specified key
        if not existing:
            # Special case for default key: try to find any binding for this user
            if key == "default" and chat_id is not None:
                any_binding = await self.collection.find_one(
                    {"user_id": user_id, "chat_id": chat_id}
                )
                if any_binding:
                    # Found another binding, delete it instead
                    result = await self.collection.delete_one(
                        {
                            "user_id": user_id,
                            "chat_id": chat_id,
                            "key": any_binding["key"],
                        }
                    )
                    return result.deleted_count > 0, any_binding["key"]
            # For non-default keys or when no alternative is found
            from botspot.core.errors import ChatBindingNotFoundError
            raise ChatBindingNotFoundError(f"No binding found with key '{key}'")

        # Normal case - delete the specific binding
        result = await self.collection.delete_one({"user_id": user_id, "key": key})
        return result.deleted_count > 0, key

    async def get_bind_chat_id(self, user_id: int, key: str = "default") -> int:
        """Get the chat ID for a user's bound chat with the given key."""
        record = await self.collection.find_one({"user_id": user_id, "key": key})
        if record is None:
            from botspot.core.errors import ChatBindingNotFoundError
            raise ChatBindingNotFoundError(f"No bound chat found for user {user_id} and key {key}")
        return record["chat_id"]

    async def get_user_bound_chats(self, user_id: int) -> List[BoundChatRecord]:
        """Get all chats bound to a user."""
        records = await self.collection.find({"user_id": user_id}).to_list(length=100)
        return [BoundChatRecord(**record) for record in records]

    async def is_bot_admin(self, chat_id: int) -> bool:
        """Check if the bot is an admin in the specified chat.

        Args:
            chat_id: The chat ID to check

        Returns:
            True if the bot is an admin, False otherwise
        """
        from botspot.utils.deps_getters import get_bot

        try:
            bot = get_bot()
            chat_member = await bot.get_chat_member(chat_id=chat_id, user_id=bot.id)
            return chat_member.status in ["administrator", "creator"]
        except Exception as e:
            logger.error(f"Error checking admin status: {e}")
            return False

    async def get_users_by_chat_id(self, chat_id: int) -> List[Dict[str, Union[int, str]]]:
        """Get all users who have bound this chat.

        Args:
            chat_id: The chat ID to get users for

        Returns:
            List of user dictionaries with user_id and binding keys
        """
        records = await self.collection.find({"chat_id": chat_id}).to_list(length=100)

        # Create a dict to collect all keys by user_id
        users_dict = {}
        for record in records:
            user_id = record["user_id"]
            key = record["key"]

            if user_id not in users_dict:
                users_dict[user_id] = {"user_id": user_id, "keys": []}
            users_dict[user_id]["keys"].append(key)

        return list(users_dict.values())


def get_chat_binder() -> ChatBinder:
    """Get the ChatBinder instance initialized in the initialize function."""
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    assert deps.chat_binder is not None, "ChatBinder is not initialized"
    return deps.chat_binder


# Wrapper functions using the global ChatBinder instance
async def bind_chat(user_id: int, chat_id: int, key: str = "default"):
    """Bind a chat to a user with the given key."""
    chat_binder = get_chat_binder()
    return await chat_binder.bind_chat(user_id, chat_id, key)


async def unbind_chat(user_id: int, key: str = "default", chat_id: Optional[int] = None):
    """Unbind a chat from a user with the given key."""
    chat_binder = get_chat_binder()
    return await chat_binder.unbind_chat(user_id, key, chat_id)


async def get_bind_chat_id(user_id: int, key: str = "default") -> int:
    """Get the chat ID for a user's bound chat with the given key."""
    chat_binder = get_chat_binder()
    return await chat_binder.get_bind_chat_id(user_id, key)


async def get_user_bound_chats(user_id: int) -> List[BoundChatRecord]:
    """Get all chats bound to a user."""
    chat_binder = get_chat_binder()
    return await chat_binder.get_user_bound_chats(user_id)


async def get_chat_binding_status(user_id: int, chat_id: int) -> List[BoundChatRecord]:
    """Get all bindings for a specific user and chat combination."""
    chat_binder = get_chat_binder()
    return await chat_binder.get_chat_binding_status(user_id, chat_id)


# async def is_bot_admin(chat_id: int) -> bool:
#     """Check if the bot is an admin in the specified chat."""
#     chat_binder = get_chat_binder()
#     return await chat_binder.is_bot_admin(chat_id)


# async def get_chat_members(chat_id: int, limit: int = 50) -> List[Dict[str, Union[int, str]]]:
#     """Get members from a chat (requires admin rights or chat_fetcher)."""
#     chat_binder = get_chat_binder()
#     return await chat_binder.get_chat_members(chat_id, limit)


async def get_users_by_chat_id(chat_id: int) -> List[Dict[str, Union[int, str]]]:
    """Get all users who have bound this chat."""
    chat_binder = get_chat_binder()
    return await chat_binder.get_users_by_chat_id(chat_id)


async def bind_chat_command_handler(message: Message):
    """Handler for the /bind_chat command."""
    chat_id = message.chat.id
    if message.from_user is None:
        await message.reply("User information is missing.")
        return

    user_id = message.from_user.id
    if message.text is None:
        await message.reply("Message text is missing.")
        return

    key = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else "default"

    try:
        record = await bind_chat(user_id, chat_id, key)

        # Include access status in the response
        access_status = (
            "✅ I have access to this chat."
            if record.has_access
            else "❌ I don't have access to this chat."
        )

        await message.reply(f"Chat bound successfully with key: {key}\n" f"{access_status}")
    except ValueError as e:
        await message.reply(f"Error: {str(e)}")


async def unbind_chat_command_handler(message: Message):
    """Handler for the /unbind_chat command."""
    if message.from_user is None:
        await message.reply("User information is missing.")
        return

    user_id = message.from_user.id
    if message.text is None:
        await message.reply("Message text is missing.")
        return

    key = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else "default"
    assert message.chat is not None
    try:
        result, deleted_key = await unbind_chat(user_id, key, chat_id=message.chat.id)
        if result:
            await message.reply(f"Chat unbound successfully with key: {deleted_key}")
        else:
            await message.reply(f"No chat was bound with key: {key}")
    except Exception as e:
        await message.reply(f"Error: {str(e)}")


async def bind_status_command_handler(message: Message):
    """Handler for the /bind_status command."""
    chat_id = message.chat.id
    if message.from_user is None:
        await message.reply("User information is missing.")
        return

    user_id = message.from_user.id

    try:
        # Get bindings for this specific chat
        bindings = await get_chat_binding_status(user_id, chat_id)

        if not bindings:
            await message.reply("This chat is not bound to you.")
            return

        # Format binding information
        if len(bindings) == 1:
            binding = bindings[0]
            # Include access status information
            access_status = (
                "✅ Bot has access" if binding.has_access else "❌ Bot doesn't have access"
            )

            await message.reply(
                f"This chat is bound to you with key: '{binding.key}'\n"
                f"Access status: {access_status}"
            )
        else:
            # For multiple bindings, create a simple list
            binding_details = []
            for binding in bindings:
                access_status = "✅ Access" if binding.has_access else "❌ No access"
                binding_details.append(f"• Key: '{binding.key}' - {access_status}")

            details_text = "\n".join(binding_details)
            await message.reply(
                f"This chat is bound to you with {len(bindings)} keys:\n{details_text}"
            )
    except Exception as e:
        logger.error(f"Error in bind_status_command_handler: {e}")
        await message.reply(f"Error checking binding status: {str(e)}")


async def async_list_chats_handler(message: Message):
    """Handler for the /list_chats command."""
    if message.from_user is None:
        await message.reply("User information is missing.")
        return

    try:
        bound_chats = await get_user_bound_chats(message.from_user.id)
        if not bound_chats:
            await message.reply("You don't have any bound chats.")
            return

        chats_info = "\n".join(
            [f"Key: {chat.key}, Chat ID: {chat.chat_id}" for chat in bound_chats]
        )
        await message.reply(f"Your bound chats:\n{chats_info}")
    except Exception as e:
        await message.reply(f"Error listing chats: {str(e)}")


# todo: ask_user_choice - list all keys and ask user to choose one
async def async_get_chat_handler(message: Message):
    """Handler for the /get_chat command."""
    if message.from_user is None:
        await message.reply("User information is missing.")
        return

    if message.text is None:
        await message.reply("Message text is missing.")
        return

    key = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else "default"

    chat_id = await get_bind_chat_id(message.from_user.id, key)
    await message.reply(f"Bound chat for key '{key}': {chat_id}")


def setup_dispatcher(dp):
    """Register chat_binder command handlers with the dispatcher."""
    # Core binding commands
    dp.message.register(bind_chat_command_handler, Command("bind_chat"))
    dp.message.register(unbind_chat_command_handler, Command("unbind_chat"))
    dp.message.register(bind_status_command_handler, Command("bind_status"))

    # Utility commands
    dp.message.register(async_list_chats_handler, Command("list_chats"))
    dp.message.register(async_get_chat_handler, Command("get_chat"))

    return dp


def initialize(settings: ChatBinderSettings) -> ChatBinder:
    """Initialize the chat_binder component.

    Args:
        settings: Configuration for the chat_binder component

    Returns:
        ChatBinder instance that will be stored in the dependency manager
    """
    from botspot.core.dependency_manager import get_dependency_manager

    # Check that MongoDB is available
    deps = get_dependency_manager()
    if not deps.botspot_settings.mongo_database.enabled:
        from botspot.core.errors import ConfigurationError
        raise ConfigurationError("MongoDB is required for chat_binder component")

    # Register commands
    from botspot.components.qol.bot_commands_menu import Visibility, add_command

    # Core bind/unbind commands are always visible if commands_visible is true
    visibility = Visibility.PUBLIC if settings.commands_visible else Visibility.HIDDEN
    add_command("bind_chat", "Bind this chat to you with an optional key", visibility=visibility)(
        bind_chat_command_handler
    )
    add_command(
        "unbind_chat", "Unbind a chat from you with an optional key", visibility=visibility
    )(unbind_chat_command_handler)

    # Utility commands are always hidden regardless of settings
    add_command(
        "bind_status",
        "Check if this chat is bound to you and with which keys",
        visibility=Visibility.HIDDEN,
    )(bind_status_command_handler)

    # These commands are registered in the component so they're available
    # even if the demo bot isn't used
    # Register utility commands as hidden
    add_command("list_chats", "List all your bound chats", visibility=Visibility.HIDDEN)(
        async_list_chats_handler
    )

    add_command("get_chat", "Get a bound chat by key", visibility=Visibility.HIDDEN)(
        async_get_chat_handler
    )

    return ChatBinder(settings)
