"""
Persistent access control for managing friends and admins lists.

Provides MongoDB-backed storage for friends and admins with fallback to environment variables.
Allows dynamic management via admin commands.
"""

from typing import TYPE_CHECKING, List, Optional

from aiogram.filters import Command
from aiogram.types import Message
from botspot.utils.admin_filter import AdminFilter
from botspot.utils.internal import get_logger
from pydantic_settings import BaseSettings

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorCollection

logger = get_logger()


class AccessControlSettings(BaseSettings):
    enabled: bool = False
    mongo_collection: str = "access_control"
    commands_visible: bool = False  # Show commands in menu (admin only anyway)

    class Config:
        env_prefix = "BOTSPOT_ACCESS_CONTROL_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


FRIENDS_KEY = "friends"
ADMINS_KEY = "admins"


class AccessControl:
    """Manages persistent friends and admins lists with MongoDB support."""

    def __init__(
        self, settings: AccessControlSettings, collection: Optional["AsyncIOMotorCollection"] = None
    ):
        self.settings = settings
        self._mongo_available = None

        if collection is None:
            try:
                from botspot.components.data.mongo_database import get_database

                db = get_database()
                logger.info(f"Initializing access_control with collection {settings.mongo_collection}")
                collection = db.get_collection(settings.mongo_collection)
                self._mongo_available = True
            except Exception as e:
                logger.warning(
                    f"MongoDB not available for access_control, will use environment variables only: {e}"
                )
                self._mongo_available = False
                collection = None

        self.collection = collection
        self._friends_cache: Optional[List[str]] = None
        self._admins_cache: Optional[List[str]] = None

    @property
    def mongo_available(self) -> bool:
        """Check if MongoDB is available."""
        return self._mongo_available or False

    async def _get_from_db(self, key: str) -> Optional[List[str]]:
        """Get a list from MongoDB."""
        if not self.mongo_available or self.collection is None:
            return None

        try:
            doc = await self.collection.find_one({"_id": key})
            if doc and "values" in doc:
                logger.debug(f"Loaded {key} from MongoDB: {doc['values']}")
                return doc["values"]
        except Exception as e:
            logger.error(f"Error loading {key} from MongoDB: {e}")
        return None

    async def _save_to_db(self, key: str, values: List[str]) -> bool:
        """Save a list to MongoDB."""
        if not self.mongo_available or self.collection is None:
            return False

        try:
            await self.collection.update_one(
                {"_id": key}, {"$set": {"values": values}}, upsert=True
            )
            logger.info(f"Saved {key} to MongoDB: {values}")
            return True
        except Exception as e:
            logger.error(f"Error saving {key} to MongoDB: {e}")
            return False

    def _get_from_env(self, key: str) -> List[str]:
        """Get a list from environment variables via botspot settings."""
        from botspot.core.dependency_manager import get_dependency_manager

        deps = get_dependency_manager()
        if key == FRIENDS_KEY:
            return deps.botspot_settings.friends
        elif key == ADMINS_KEY:
            return deps.botspot_settings.admins
        return []

    async def get_friends(self) -> List[str]:
        """Get friends list, preferring MongoDB over environment variables."""
        if self._friends_cache is not None:
            return self._friends_cache

        friends_from_db = await self._get_from_db(FRIENDS_KEY)

        if friends_from_db is not None:
            logger.info(
                f"Loaded {len(friends_from_db)} friends from MongoDB, ignoring environment variables"
            )
            if len(friends_from_db) > 0:
                logger.warning(
                    "⚠️  Friends list loaded from MongoDB. Environment variable BOTSPOT_FRIENDS_STR will be ignored."
                )
            self._friends_cache = friends_from_db
            return friends_from_db

        friends_from_env = self._get_from_env(FRIENDS_KEY)
        logger.info(
            f"No friends data in MongoDB, initializing from environment: {friends_from_env}"
        )

        if self.mongo_available and friends_from_env:
            await self._save_to_db(FRIENDS_KEY, friends_from_env)

        self._friends_cache = friends_from_env
        return friends_from_env

    async def get_admins(self) -> List[str]:
        """Get admins list, preferring MongoDB over environment variables."""
        if self._admins_cache is not None:
            return self._admins_cache

        admins_from_db = await self._get_from_db(ADMINS_KEY)

        if admins_from_db is not None:
            logger.info(
                f"Loaded {len(admins_from_db)} admins from MongoDB, ignoring environment variables"
            )
            if len(admins_from_db) > 0:
                logger.warning(
                    "⚠️  Admins list loaded from MongoDB. Environment variable BOTSPOT_ADMINS_STR will be ignored."
                )
            self._admins_cache = admins_from_db
            return admins_from_db

        admins_from_env = self._get_from_env(ADMINS_KEY)
        logger.info(
            f"No admins data in MongoDB, initializing from environment: {admins_from_env}"
        )

        if self.mongo_available and admins_from_env:
            await self._save_to_db(ADMINS_KEY, admins_from_env)

        self._admins_cache = admins_from_env
        return admins_from_env

    async def add_friend(self, username: str) -> bool:
        """Add a friend to the friends list."""
        if username.isdigit():
            normalized = username
        else:
            normalized = username if username.startswith("@") else f"@{username}"

        friends = await self.get_friends()

        if normalized in friends:
            logger.info(f"Friend {normalized} already in list")
            return False

        friends.append(normalized)
        self._friends_cache = friends

        if self.mongo_available:
            success = await self._save_to_db(FRIENDS_KEY, friends)
            if success:
                logger.info(f"Added friend {normalized} to MongoDB")
            return success
        else:
            logger.warning(
                f"Added friend {normalized} to in-memory cache only (MongoDB not available)"
            )
            return True

    async def remove_friend(self, username: str) -> bool:
        """Remove a friend from the friends list."""
        if username.isdigit():
            normalized = username
        else:
            normalized = username if username.startswith("@") else f"@{username}"

        friends = await self.get_friends()

        if normalized not in friends:
            logger.info(f"Friend {normalized} not in list")
            return False

        friends.remove(normalized)
        self._friends_cache = friends

        if self.mongo_available:
            success = await self._save_to_db(FRIENDS_KEY, friends)
            if success:
                logger.info(f"Removed friend {normalized} from MongoDB")
            return success
        else:
            logger.warning(
                f"Removed friend {normalized} from in-memory cache only (MongoDB not available)"
            )
            return True


def get_access_control() -> AccessControl:
    """Get the AccessControl instance from dependency manager."""
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    assert deps.access_control is not None, "AccessControl is not initialized"
    return deps.access_control


# Wrapper functions
async def get_friends() -> List[str]:
    """Get the current friends list."""
    access_control = get_access_control()
    return await access_control.get_friends()


async def add_friend(username: str) -> bool:
    """Add a friend to the friends list."""
    access_control = get_access_control()
    return await access_control.add_friend(username)


async def remove_friend(username: str) -> bool:
    """Remove a friend from the friends list."""
    access_control = get_access_control()
    return await access_control.remove_friend(username)


# Command handlers
async def add_friend_command_handler(message: Message):
    """Handler for /add_friend command."""
    from aiogram.fsm.context import FSMContext
    from botspot.utils.user_ops import get_username_from_command_or_dialog

    assert message.from_user is not None

    # Get FSM context from middleware
    state: FSMContext = message.bot.get("state")  # type: ignore

    username = await get_username_from_command_or_dialog(
        message=message,
        state=state,
        prompt="Please send the username or forward a message from the user you want to add as friend:",
        timeout=60,
    )

    if username is None:
        await message.reply("❌ Failed to get username. Operation cancelled.")
        return

    try:
        success = await add_friend(username)
        if success:
            await message.reply(f"✅ Successfully added {username} to friends list!")
        else:
            await message.reply(f"ℹ️ {username} is already in the friends list.")
    except Exception as e:
        logger.error(f"Error adding friend {username}: {e}")
        await message.reply(f"❌ Error adding friend: {str(e)}")


async def remove_friend_command_handler(message: Message):
    """Handler for /remove_friend command."""
    from aiogram.fsm.context import FSMContext
    from botspot.utils.user_ops import get_username_from_command_or_dialog

    assert message.from_user is not None

    state: FSMContext = message.bot.get("state")  # type: ignore

    username = await get_username_from_command_or_dialog(
        message=message,
        state=state,
        prompt="Please send the username or forward a message from the user you want to remove from friends:",
        timeout=60,
    )

    if username is None:
        await message.reply("❌ Failed to get username. Operation cancelled.")
        return

    try:
        success = await remove_friend(username)
        if success:
            await message.reply(f"✅ Successfully removed {username} from friends list!")
        else:
            await message.reply(f"ℹ️ {username} was not in the friends list.")
    except Exception as e:
        logger.error(f"Error removing friend {username}: {e}")
        await message.reply(f"❌ Error removing friend: {str(e)}")


async def list_friends_command_handler(message: Message):
    """Handler for /list_friends command."""
    assert message.from_user is not None

    try:
        friends = await get_friends()

        if not friends:
            await message.reply("ℹ️ No friends in the list.")
            return

        response = "<b>👥 Friends List:</b>\n\n"
        for i, friend in enumerate(friends, 1):
            response += f"{i}. {friend}\n"

        response += f"\n<i>Total: {len(friends)} friends</i>"

        await message.reply(response)

    except Exception as e:
        logger.error(f"Error listing friends: {e}")
        await message.reply(f"❌ Error listing friends: {str(e)}")


def setup_dispatcher(dp):
    """Register access_control command handlers with the dispatcher."""
    dp.message.register(add_friend_command_handler, Command("add_friend"), AdminFilter())
    dp.message.register(remove_friend_command_handler, Command("remove_friend"), AdminFilter())
    dp.message.register(list_friends_command_handler, Command("list_friends"), AdminFilter())

    return dp


def initialize(settings: AccessControlSettings) -> AccessControl:
    """Initialize the access_control component.

    Args:
        settings: Configuration for the access_control component

    Returns:
        AccessControl instance that will be stored in the dependency manager
    """
    from botspot.components.qol.bot_commands_menu import Visibility, add_command

    # Register commands (admin-only)
    visibility = Visibility.ADMIN_ONLY if settings.commands_visible else Visibility.HIDDEN

    add_command("add_friend", "Add a friend to the bot (admin only)", visibility=visibility)(
        add_friend_command_handler
    )
    add_command("remove_friend", "Remove a friend from the bot (admin only)", visibility=visibility)(
        remove_friend_command_handler
    )
    add_command("list_friends", "List all friends (admin only)", visibility=visibility)(
        list_friends_command_handler
    )

    return AccessControl(settings)
