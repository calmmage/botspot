import traceback
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, Optional, Type

from aiogram import BaseMiddleware, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message, TelegramObject
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from botspot.utils import compare_users
from botspot.utils.admin_filter import AdminFilter
from botspot.utils.deps_getters import get_database, get_user_manager
from botspot.utils.internal import get_logger

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase

    from botspot.core.botspot_settings import BotspotSettings

logger = get_logger()


class UserType(str, Enum):
    """User type enumeration"""

    ADMIN = "admin"
    FRIEND = "friend"
    REGULAR = "regular"


class User(BaseModel):
    """Base User model for storing user information."""

    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    timezone: Optional[str] = "UTC"
    # location: Optional[dict] = None  # Can store coordinates or location name
    user_type: UserType = UserType.REGULAR
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_active: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # settings: dict = Field(default_factory=dict)  # For component-specific settings

    @property
    def full_name(self) -> str:
        """Get user's full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.username or str(self.user_id)


class UserManager:
    """Manager class for user operations"""

    def __init__(
        self,
        db: "AsyncIOMotorDatabase",
        collection: str,
        user_class: Type[User],
        settings: Optional["BotspotSettings"] = None,
    ):
        self.db = db
        self.collection = collection
        self.user_class = user_class
        from botspot.core.dependency_manager import get_dependency_manager

        self.settings = settings or get_dependency_manager().botspot_settings

    # todo: add functionality for searching users - by name etc.
    async def add_user(self, user: User) -> bool:
        """Add or update user"""
        try:
            # Set user type based on settings
            if user.user_id in self.settings.admins:
                user.user_type = UserType.ADMIN
            elif any([compare_users(user, friend) for friend in self.settings.friends]):
                user.user_type = UserType.FRIEND
            else:
                user.user_type = UserType.REGULAR

            existing = await self.get_user(user.user_id)
            if existing:
                raise ValueError("User already exists - cannot add")

            await self.users_collection.update_one(
                {"user_id": user.user_id}, {"$set": user.model_dump()}, upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to add user {user.user_id}: {e}")
            logger.debug(traceback.format_exc())
            return False

    async def update_user(self, user_id: int, field: str, value: Any) -> bool:
        """Update a user's field"""
        try:
            await self.users_collection.update_one({"user_id": user_id}, {"$set": {field: value}})
            logger.debug(f"Updated user {user_id} field {field} to {value}")
            return True
        except Exception as e:
            logger.error(f"Failed to update user {user_id} field {field}: {e}")
            return False

    # todo: make sure this works with username as well
    async def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        data = await self.users_collection.find_one({"user_id": user_id})
        return self.user_class(**data) if data else None

    async def has_user(self, user_id: int) -> bool:
        """Check if user exists in the database"""
        return bool(await self.get_user(user_id))

    @property
    def users_collection(self) -> "AsyncIOMotorCollection":
        return self.users_collection

    async def find_user(
        self,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        phone: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> Optional[User]:
        """Find user by any of the fields"""
        if not any([user_id, username, phone, first_name, last_name]):
            raise ValueError("find_user requires at least one of the fields")
        # if direct fields are provided - use them
        if any([user_id, username, phone]):
            return await self.users_collection.find_one(
                {
                    "$or": [
                        {"user_id": user_id} if user_id else None,
                        {"username": username} if username else None,
                        {"phone": phone} if phone else None,
                    ]
                }
            )
        # if not - use fuzzy match on name
        return await self.users_collection.find_one(
            {
                "$and": [
                    {"first_name": first_name} if first_name else None,
                    {"last_name": last_name} if last_name else None,
                ]
            }
        )

    async def update_last_active(self, user_id: int) -> None:
        """Update user's last active timestamp"""
        await self.users_collection.update_one(
            {"user_id": user_id}, {"$set": {"last_active": datetime.now(timezone.utc)}}
        )

    # todo: make sure this works with username as well
    async def make_friend(self, user_id: int) -> bool:
        """Make user a friend (admin only operation)"""
        try:
            user = await self.get_user(user_id)
            if not user:
                return False

            user.user_type = UserType.FRIEND
            await self.users_collection.update_one(
                {"user_id": user_id}, {"$set": {"user_type": UserType.FRIEND}}
            )
            return True
        except Exception:
            return False

    async def sync_user_types(self) -> None:
        """
        Sync user types with current settings.
        Updates only existing users:
        - Admins: promote/demote based on settings
        - Friends: promote only (no automatic demotion)
        """
        try:
            # Update admins
            if self.settings.admins:
                # Promote current admins
                result = await self.users_collection.update_many(
                    {"user_id": {"$in": list(self.settings.admins)}},
                    {"$set": {"user_type": UserType.ADMIN}},
                )
                if result.modified_count:
                    logger.info(f"Promoted {result.modified_count} users to admin")

                # Demote former admins
                result = await self.users_collection.update_many(
                    {
                        "user_id": {"$nin": list(self.settings.admins)},
                        "user_type": UserType.ADMIN,
                    },
                    {"$set": {"user_type": UserType.REGULAR}},
                )
                if result.modified_count:
                    logger.info(f"Demoted {result.modified_count} admins to regular users")

            # Update friends (only promote, don't demote)
            if self.settings.friends:
                await self._promote_friends()
        except Exception as e:
            logger.error(f"Failed to sync user types: {e}")
            raise  # Re-raise to handle in startup

    async def _promote_friends(self):
        # handle int and str cases
        friends_ids = []
        friends_usernames = []
        for friend in self.settings.friends:
            try:
                friends_ids.append(int(friend))
            except ValueError:
                friends_usernames.append(friend.lstrip("@"))
        res = 0
        if friends_ids:
            result = await self.users_collection.update_many(
                {
                    "user_id": {"$in": friends_ids},
                    "user_type": UserType.REGULAR,  # Only update if regular user
                },
                {"$set": {"user_type": UserType.FRIEND}},
            )
            res += result.modified_count
        if friends_usernames:
            result = await self.users_collection.update_many(
                {
                    "username": {"$in": friends_usernames},
                    "user_type": UserType.REGULAR,  # Only update if regular user
                },
                {"$set": {"user_type": UserType.FRIEND}},
            )
            res += result.modified_count
        if res:
            logger.info(f"Promoted {res} users to friends")


class UserTrackingMiddleware(BaseMiddleware):
    """Middleware to track users and ensure they're registered."""

    def __init__(self, cache_ttl: int = 300):
        self._cache: dict[int, datetime] = {}
        self._cache_ttl = cache_ttl
        super().__init__()

    def _is_cache_valid(self, user_id: int) -> bool:
        """Check if user is in cache and cache is still valid"""
        if user_id not in self._cache:
            return False

        last_update = self._cache[user_id]
        now = datetime.now(timezone.utc)
        return (now - last_update).total_seconds() < self._cache_ttl

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Only process messages with user information
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id

            # Skip DB operations if user was recently processed
            if not self._is_cache_valid(user_id):
                user_manager = get_user_manager()
                if not await user_manager.has_user(user_id):
                    user = user_manager.user_class(
                        user_id=user_id,
                        username=event.from_user.username,
                        first_name=event.from_user.first_name,
                        last_name=event.from_user.last_name,
                    )
                    await user_manager.add_user(user)
                await user_manager.update_last_active(user_id)

                # Update cache
                self._cache[user_id] = datetime.now(timezone.utc)

        return await handler(event, data)


class UserDataSettings(BaseSettings):
    """User data component settings"""

    enabled: bool = False
    middleware_enabled: bool = True
    collection: str = "botspot_users"
    cache_ttl: int = 300  # Cache TTL in seconds (5 minutes by default)
    user_types_enabled: bool = True  # New setting

    class Config:
        env_prefix = "BOTSPOT_USER_DATA_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


def initialize(user_class=None, **kwargs) -> UserManager:
    """Initialize the user data component"""
    from botspot.core.dependency_manager import get_dependency_manager

    settings = UserDataSettings(**kwargs)
    if not settings.enabled:
        return None

    db = get_database()
    deps = get_dependency_manager()

    if user_class is None:
        user_class = User

    return UserManager(
        db=db,
        collection=settings.collection,
        user_class=user_class,
        settings=deps.botspot_settings,
    )


def setup_dispatcher(dp: Dispatcher, **kwargs):
    """Setup the user data component"""
    settings = UserDataSettings(**kwargs)
    if not settings.enabled:
        return

    if settings.middleware_enabled:
        dp.message.middleware(UserTrackingMiddleware(cache_ttl=settings.cache_ttl))

    if settings.user_types_enabled:
        from botspot.components import bot_commands_menu
        from botspot.components.bot_commands_menu import Visibility

        router = Router(name="user_data")
        router.message.filter(AdminFilter())  # Only admins can use these commands

        @bot_commands_menu.add_command("make_friend", visibility=Visibility.ADMIN_ONLY)
        @router.message(Command("make_friend"))
        async def make_friend_cmd(message: Message):
            """Make a user a friend (admin only command)"""
            if not message.reply_to_message:
                await message.answer("Reply to a user's message to make them a friend")
                return

            user_id = message.reply_to_message.from_user.id
            user_manager = get_user_manager()

            if await user_manager.make_friend(user_id):
                await message.answer(f"User {user_id} is now a friend!")
            else:
                await message.answer("Failed to update user type")

        dp.include_router(router)

    async def sync_types():
        from botspot.utils.deps_getters import get_user_manager

        manager = get_user_manager()

        await manager.sync_user_types()

    dp.startup.register(sync_types)
