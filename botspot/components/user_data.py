from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, Optional, Type

from aiogram import BaseMiddleware, Dispatcher
from aiogram.types import Message, TelegramObject
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from botspot.utils.deps_getters import get_database, get_user_manager

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorDatabase


class User(BaseModel):
    """Base User model for storing user information."""

    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    timezone: Optional[str] = "UTC"
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
            self, db: "AsyncIOMotorDatabase", collection: str, user_class: Type[User]
    ):
        self.db = db
        self.collection = collection
        self.user_class = user_class

    async def add_user(self, user: User) -> bool:
        """Add or update user"""
        try:
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

    async def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        data = await self.db[self.collection].find_one({"user_id": user_id})
        return self.user_class(**data) if data else None

    async def update_last_active(self, user_id: int) -> None:
        """Update user's last active timestamp"""
        await self.db[self.collection].update_one(
            {"user_id": user_id}, {"$set": {"last_active": datetime.now(timezone.utc)}}
        )


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

    enabled: bool = True
    middleware_enabled: bool = True
    collection: str = "botspot_users"
    user_class: Type[User] = User
    cache_ttl: int = 300  # Cache TTL in seconds (5 minutes by default)

    class Config:
        env_prefix = "BOTSPOT_USER_DATA_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


def init_component(**kwargs) -> UserManager:
    """Initialize the user data component"""
    settings = UserDataSettings(**kwargs)
    if not settings.enabled:
        return None

    db = get_database()
    return UserManager(
        db=db, collection=settings.collection, user_class=settings.user_class
    )


def setup_component(dp: Dispatcher, **kwargs):
    """Setup the user data component"""
    settings = UserDataSettings(**kwargs)
    if not settings.enabled:
        return

    if settings.middleware_enabled:
        dp.message.middleware(UserTrackingMiddleware(cache_ttl=settings.cache_ttl))
