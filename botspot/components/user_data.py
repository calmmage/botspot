from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, Optional, Type

from aiogram import BaseMiddleware, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message, TelegramObject
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from botspot.utils.admin_filter import AdminFilter
from botspot.utils.deps_getters import get_database, get_user_manager
from botspot.utils.internal import get_logger

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorDatabase

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
    user_type: UserType = UserType.REGULAR
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_active: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def full_name(self) -> str:
        """Get user's full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.username or str(self.user_id)

    def merge_with(self, other: "User") -> bool:
        """
        Merge another user's data into this one.
        Returns True if merge was successful, False if there were conflicts.
        """
        for field in self.model_fields:
            other_value = getattr(other, field)
            if other_value is not None:
                current_value = getattr(self, field)
                if current_value is None or field in [
                    "last_active",
                    "username",
                    "first_name",
                    "last_name",
                ]:
                    setattr(self, field, other_value)
                elif current_value != other_value and field not in [
                    "user_id",
                    "created_at",
                ]:
                    return False
        return True


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
            elif user.user_id in self.settings.friends:
                user.user_type = UserType.FRIEND
            else:
                user.user_type = UserType.REGULAR

            existing = await self.get_user(user.user_id)
            if existing:
                if not existing.merge_with(user):
                    raise ValueError("Conflict in user data during merge")
                user = existing

            await self.db[self.collection].update_one(
                {"user_id": user.user_id}, {"$set": user.model_dump()}, upsert=True
            )
            return True
        except Exception:
            return False

    # todo: make sure this works with username as well
    async def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        data = await self.db[self.collection].find_one({"user_id": user_id})
        return self.user_class(**data) if data else None

    async def update_last_active(self, user_id: int) -> None:
        """Update user's last active timestamp"""
        await self.db[self.collection].update_one(
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
            await self.db[self.collection].update_one(
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
                result = await self.db[self.collection].update_many(
                    {"user_id": {"$in": list(self.settings.admins)}},
                    {"$set": {"user_type": UserType.ADMIN}},
                )
                if result.modified_count:
                    logger.info(f"Promoted {result.modified_count} users to admin")

                # Demote former admins
                result = await self.db[self.collection].update_many(
                    {
                        "user_id": {"$nin": list(self.settings.admins)},
                        "user_type": UserType.ADMIN,
                    },
                    {"$set": {"user_type": UserType.REGULAR}},
                )
                if result.modified_count:
                    logger.info(
                        f"Demoted {result.modified_count} admins to regular users"
                    )

            # Update friends (only promote, don't demote)
            if self.settings.friends:
                result = await self.db[self.collection].update_many(
                    {
                        "user_id": {"$in": list(self.settings.friends)},
                        "user_type": UserType.REGULAR,  # Only update if regular user
                    },
                    {"$set": {"user_type": UserType.FRIEND}},
                )
                if result.modified_count:
                    logger.info(f"Promoted {result.modified_count} users to friends")

        except Exception as e:
            logger.error(f"Failed to sync user types: {e}")
            raise  # Re-raise to handle in startup


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
    user_class: Type[User] = User
    cache_ttl: int = 300  # Cache TTL in seconds (5 minutes by default)
    user_types_enabled: bool = True  # New setting

    class Config:
        env_prefix = "BOTSPOT_USER_DATA_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


def init_component(**kwargs) -> UserManager:
    """Initialize the user data component"""
    from botspot.core.dependency_manager import get_dependency_manager

    settings = UserDataSettings(**kwargs)
    if not settings.enabled:
        return None

    db = get_database()
    deps = get_dependency_manager()

    return UserManager(
        db=db,
        collection=settings.collection,
        user_class=settings.user_class,
        settings=deps.botspot_settings,
    )


def setup_component(dp: Dispatcher, **kwargs):
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
