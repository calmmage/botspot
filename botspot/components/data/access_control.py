"""
Persistent access control for managing friends and admins lists.

Provides MongoDB-backed storage for friends and admins with fallback to environment variables.
Allows dynamic management via admin commands.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Literal, Optional

from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from botspot.components.middlewares.i18n import t
from botspot.utils.admin_filter import AdminFilter
from botspot.utils.internal import get_logger
from pydantic_settings import BaseSettings

if TYPE_CHECKING:
    from pymongo.asynchronous.collection import AsyncCollection  # noqa: vulture

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

_ENV_VAR = {FRIENDS_KEY: "BOTSPOT_FRIENDS_STR", ADMINS_KEY: "BOTSPOT_ADMINS_STR"}


@dataclass
class AccessListDiff:
    """Difference between the MongoDB list and the env list. Entries keep their original spelling."""

    only_in_db: List[str]
    only_in_env: List[str]
    same: bool = field(init=False)

    def __post_init__(self):
        self.same = not self.only_in_db and not self.only_in_env


def _normalize_entry(entry) -> str:
    """Compare key: stripped, no leading '@', lowercase. Numeric ids compare as strings."""
    return str(entry).strip().lstrip("@").lower()


def diff_access_lists(db_list: List[str], env_list: List[str]) -> AccessListDiff:
    """Pure diff of two access lists ('@abc' == 'abc' == '@ABC', ids compared as strings)."""
    db_keys = {_normalize_entry(x) for x in db_list}
    env_keys = {_normalize_entry(x) for x in env_list}
    return AccessListDiff(
        only_in_db=[x for x in db_list if _normalize_entry(x) not in env_keys],
        only_in_env=[x for x in env_list if _normalize_entry(x) not in db_keys],
    )


class AccessControl:
    """Manages persistent friends and admins lists with MongoDB support."""

    def __init__(
        self, settings: AccessControlSettings, collection: Optional["AsyncCollection"] = None
    ):
        self.settings = settings
        self._mongo_available = None

        if collection is None:
            try:
                from botspot.components.data.mongo_database import get_database

                db = get_database()
                logger.info(
                    f"Initializing access_control with collection {settings.mongo_collection}"
                )
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
        # Where each list came from and how it compared to the env var (filled on first load).
        self.friends_source: Literal["mongo", "env"] = "env"
        self.admins_source: Literal["mongo", "env"] = "env"
        self.friends_diff: Optional[AccessListDiff] = None
        self.admins_diff: Optional[AccessListDiff] = None

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

    def _compare_with_env(self, key: str, db_list: List[str]) -> Optional[AccessListDiff]:
        """Log how the MongoDB list relates to the env var. Warn only when they differ."""
        env_var = _ENV_VAR[key]
        env_list = self._get_from_env(key)
        if not env_list:
            logger.info(f"Loaded {len(db_list)} {key} from MongoDB ({env_var} unset)")
            return None

        diff = diff_access_lists(db_list, env_list)
        if diff.same:
            logger.info(f"Loaded {len(db_list)} {key} from MongoDB (matches {env_var})")
            return diff

        parts = []
        if diff.only_in_db:
            parts.append(f"only in MongoDB: {', '.join(diff.only_in_db)}")
        if diff.only_in_env:
            parts.append(f"only in env: {', '.join(diff.only_in_env)}")
        logger.warning(
            f"{key.capitalize()} list from MongoDB differs from {env_var} — "
            f"{'; '.join(parts)}. MongoDB wins."
        )
        return diff

    def get_access_report(self) -> Dict[str, dict]:
        """Source, count and env diff for both lists, for consumers such as startup reports."""

        def _entry(cache, source, diff):
            return {
                "source": source,
                "count": len(cache or []),
                "only_in_db": list(diff.only_in_db) if diff else [],
                "only_in_env": list(diff.only_in_env) if diff else [],
            }

        return {
            "friends": _entry(self._friends_cache, self.friends_source, self.friends_diff),
            "admins": _entry(self._admins_cache, self.admins_source, self.admins_diff),
        }

    def get_friends_cached(self) -> Optional[List[str]]:
        """Sync access to cached friends list. None if not yet loaded."""
        return self._friends_cache

    def get_admins_cached(self) -> Optional[List[str]]:
        """Sync access to cached admins list. None if not yet loaded."""
        return self._admins_cache

    async def get_friends(self) -> List[str]:
        """Get friends list, preferring MongoDB over environment variables."""
        if self._friends_cache is not None:
            return self._friends_cache

        friends_from_db = await self._get_from_db(FRIENDS_KEY)

        if friends_from_db is not None:
            self.friends_source = "mongo"
            self.friends_diff = self._compare_with_env(FRIENDS_KEY, friends_from_db)
            self._friends_cache = friends_from_db
            return friends_from_db

        friends_from_env = self._get_from_env(FRIENDS_KEY)
        logger.info(
            f"No friends data in MongoDB, initializing from environment: {friends_from_env}"
        )

        if self.mongo_available and friends_from_env:
            await self._save_to_db(FRIENDS_KEY, friends_from_env)

        self.friends_source = "env"
        self._friends_cache = friends_from_env
        return friends_from_env

    async def get_admins(self) -> List[str]:
        """Get admins list, preferring MongoDB over environment variables."""
        if self._admins_cache is not None:
            return self._admins_cache

        admins_from_db = await self._get_from_db(ADMINS_KEY)

        if admins_from_db is not None:
            self.admins_source = "mongo"
            self.admins_diff = self._compare_with_env(ADMINS_KEY, admins_from_db)
            self._admins_cache = admins_from_db
            return admins_from_db

        admins_from_env = self._get_from_env(ADMINS_KEY)
        logger.info(f"No admins data in MongoDB, initializing from environment: {admins_from_env}")

        if self.mongo_available and admins_from_env:
            await self._save_to_db(ADMINS_KEY, admins_from_env)

        self.admins_source = "env"
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
async def add_friend_command_handler(message: Message, state: FSMContext):
    """Handler for /add_friend command."""
    from botspot.utils.user_ops import get_username_from_command_or_dialog

    assert message.from_user is not None

    username = await get_username_from_command_or_dialog(
        message=message,
        state=state,
        prompt="Please send the username or forward a message from the user you want to add as friend:",
        timeout=60,
    )

    if username is None:
        await message.reply(t("access_control.add_friend_failed"))
        return

    try:
        success = await add_friend(username)
        if success:
            await message.reply(t("access_control.add_friend_success", username=username))
        else:
            await message.reply(t("access_control.add_friend_already_exists", username=username))
    except Exception as e:
        logger.error(f"Error adding friend {username}: {e}")
        await message.reply(t("access_control.add_friend_error", error=str(e)))


async def remove_friend_command_handler(message: Message, state: FSMContext):
    """Handler for /remove_friend command."""
    from botspot.utils.user_ops import get_username_from_command_or_dialog

    assert message.from_user is not None

    username = await get_username_from_command_or_dialog(
        message=message,
        state=state,
        prompt="Please send the username or forward a message from the user you want to remove from friends:",
        timeout=60,
    )

    if username is None:
        await message.reply(t("access_control.remove_friend_failed"))
        return

    try:
        success = await remove_friend(username)
        if success:
            await message.reply(t("access_control.remove_friend_success", username=username))
        else:
            await message.reply(t("access_control.remove_friend_not_found", username=username))
    except Exception as e:
        logger.error(f"Error removing friend {username}: {e}")
        await message.reply(t("access_control.remove_friend_error", error=str(e)))


async def list_friends_command_handler(message: Message):
    """Handler for /list_friends command."""
    assert message.from_user is not None

    try:
        friends = await get_friends()

        if not friends:
            await message.reply(t("access_control.list_friends_empty"))
            return

        response = t("access_control.list_friends_header")
        for i, friend in enumerate(friends, 1):
            response += f"{i}. {friend}\n"

        response += t("access_control.list_friends_total", count=len(friends))

        await message.reply(response)

    except Exception as e:
        logger.error(f"Error listing friends: {e}")
        await message.reply(t("access_control.list_friends_error", error=str(e)))


def setup_dispatcher(dp):
    """Register access_control command handlers with the dispatcher."""
    dp.message.register(add_friend_command_handler, Command("add_friend"), AdminFilter())
    dp.message.register(remove_friend_command_handler, Command("remove_friend"), AdminFilter())
    dp.message.register(list_friends_command_handler, Command("list_friends"), AdminFilter())

    async def _warm_cache():
        """Populate access_control caches on startup so sync is_friend/is_admin work."""
        try:
            ac = get_access_control()
            await ac.get_friends()
            await ac.get_admins()
            logger.info("Access control caches warmed")
        except Exception as e:
            logger.warning(f"Failed to warm access control caches: {e}")

    dp.startup.register(_warm_cache)

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
    add_command(
        "remove_friend", "Remove a friend from the bot (admin only)", visibility=visibility
    )(remove_friend_command_handler)
    add_command("list_friends", "List all friends (admin only)", visibility=visibility)(
        list_friends_command_handler
    )

    return AccessControl(settings)
