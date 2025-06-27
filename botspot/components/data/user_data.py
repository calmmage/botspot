from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, Generic, Optional, Type, TypeVar

from aiogram import BaseMiddleware, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message, TelegramObject
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from botspot.utils.admin_filter import AdminFilter
from botspot.utils.internal import get_logger

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorCollection  # noqa: F401
    from motor.motor_asyncio import AsyncIOMotorDatabase  # noqa: F401

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


# Define a type variable that represents any subclass of User
UserT = TypeVar("UserT", bound=User)


class UserManager(Generic[UserT]):
    """Manager class for user operations"""

    def __init__(
        self,
        db: "AsyncIOMotorDatabase",
        collection: str,
        user_class: Type[UserT],
        settings: Optional["BotspotSettings"] = None,
    ):
        self.db = db
        self.collection = collection
        self.user_class = user_class
        from botspot.core.dependency_manager import get_dependency_manager

        self.settings = settings or get_dependency_manager().botspot_settings

    # todo: add functionality for searching users - by name etc.
    async def add_user(self, user: UserT) -> bool:
        """Add or update user"""
        from botspot.utils import compare_users

        # Set user type based on settings
        if any([compare_users(user, friend) for friend in self.settings.admins]):
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

    async def update_user(self, user_id: int, field: str, value: Any) -> bool:
        """Update a user's field"""
        await self.users_collection.update_one({"user_id": user_id}, {"$set": {field: value}})
        logger.debug(f"Updated user {user_id} field {field} to {value}")
        return True

    # todo: make sure this works with username as well
    async def get_user(self, user_id: int) -> Optional[UserT]:
        """Get user by ID"""
        data = await self.users_collection.find_one({"user_id": user_id})
        return self.user_class(**data) if data else None

    async def has_user(self, user_id: int) -> bool:
        """Check if user exists in the database"""
        return bool(await self.get_user(user_id))

    @property
    def users_collection(self) -> "AsyncIOMotorCollection":
        return self.db[self.collection]

    async def get_users(self, query: Optional[dict] = None) -> list[UserT]:
        """Get all users matching the query"""
        if query is None:
            query = {}
        data = await self.users_collection.find(query).to_list()
        return [self.user_class(**item) for item in data]

    async def find_user(
        self,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        phone: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> Optional[UserT]:
        """Find user by any of the fields"""
        if not any([user_id, username, phone, first_name, last_name]):
            raise ValueError("find_user requires at least one of the fields")

        # Build query conditions
        query = {}

        # If direct fields are provided - use them
        if any([user_id, username, phone]):
            or_conditions = []
            if user_id:
                or_conditions.append({"user": user_id})
            if username:
                or_conditions.append({"username": username})
            if phone:
                or_conditions.append({"phone": phone})

            if or_conditions:
                query["$or"] = or_conditions
        # If not - use match on name fields
        elif first_name or last_name:
            if first_name:
                query["first_name"] = first_name
            if last_name:
                query["last_name"] = last_name

        # Execute query
        result = await self.users_collection.find_one(query)

        # Convert to User model if result found
        if result:
            return self.user_class(**result)
        return None

    async def update_last_active(self, user_id: int) -> None:
        """Update user's last active timestamp"""
        await self.users_collection.update_one(
            {"user_id": user_id}, {"$set": {"last_active": datetime.now(timezone.utc)}}
        )

    # todo: make sure this works with username as well
    async def make_friend(self, user_id: int) -> bool:
        """Make user a friend (admin only operation)"""
        user = await self.get_user(user_id)
        if not user:
            return False

        user.user_type = UserType.FRIEND
        await self.users_collection.update_one(
            {"user_id": user_id}, {"$set": {"user_type": UserType.FRIEND}}
        )
        return True

    async def sync_user_types(self) -> None:
        """
        Sync user types with current settings.
        Updates only existing users:
        - Admins: promote/demote based on settings
        - Friends: promote only (no automatic demotion)
        """
        # Update admins
        if self.settings.admins:
            # Convert usernames to user IDs
            admin_ids = []
            for admin in self.settings.admins:
                if admin.startswith("@"):
                    username = admin[1:]  # Remove the '@' prefix
                    user = await self.users_collection.find_one({"username": username})
                    if user and "user_id" in user:
                        admin_ids.append(user["user_id"])
                        logger.info(f"Mapped username {admin} to user_id {user['user_id']}")
                    else:
                        logger.warning(f"Could not find user_id for username {admin}")
                else:
                    # Assume it's already a user_id
                    try:
                        admin_ids.append(int(admin))
                    except ValueError:
                        logger.warning(f"Invalid user_id format in admin list: {admin}")

            # Promote current admins
            result = await self.users_collection.update_many(
                {"user_id": {"$in": admin_ids}},
                {"$set": {"user_type": UserType.ADMIN}},
            )
            if result.modified_count:
                logger.info(f"Promoted {result.modified_count} users to admin")

            # Demote former admins
            result = await self.users_collection.update_many(
                {
                    "user_id": {"$nin": admin_ids},
                    "user_type": UserType.ADMIN,
                },
                {"$set": {"user_type": UserType.REGULAR}},
            )
            if result.modified_count:
                logger.info(f"Demoted {result.modified_count} admins to regular users")

        # Update friends (only promote, don't demote)
        if self.settings.friends:
            await self._promote_friends()

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
                # Direct access to dependency_manager to avoid circular imports
                from botspot.core.dependency_manager import get_dependency_manager

                user_manager = get_dependency_manager().user_manager
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


def initialize(settings: "BotspotSettings", user_class=None) -> UserManager:
    """Initialize the user data component.

    Args:
        settings: Botspot settings
        user_class: Optional custom User class to use

    Returns:
        UserManager instance

    Raises:
        RuntimeError: If MongoDB is not enabled or initialized
        ImportError: If motor package is not installed
    """
    # Check that motor is installed
    try:
        import motor  # noqa: F401
    except ImportError:
        from botspot.utils.internal import get_logger

        logger = get_logger()
        logger.error(
            "motor package is not installed. Please install it to use the user_data component."
        )
        raise ImportError(
            "motor package is not installed. Please install it with 'poetry add motor' or 'pip install motor' to use the user_data component."
        )

    # Check that MongoDB component is enabled
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    if not deps.botspot_settings.mongo_database.enabled:
        from botspot.utils.internal import get_logger

        logger = get_logger()
        logger.error("MongoDB is not enabled. User data component requires it.")
        raise RuntimeError("MongoDB is not enabled. BOTSPOT_MONGO_DATABASE_ENABLED=true in .env")

    # Get database and ensure we can access it
    from botspot.components.data.mongo_database import get_database

    try:
        db = get_database()
        # Simple existence check to verify database is accessible
        _ = db.name
    except Exception as e:
        from botspot.utils.internal import get_logger

        logger = get_logger()
        logger.error(f"Failed to connect to MongoDB: {str(e)}")
        raise RuntimeError(f"MongoDB connection failed: {str(e)}")

    if user_class is None:
        user_class = User

    return UserManager(
        db=db,
        collection=settings.user_data.collection,
        user_class=user_class,
        settings=settings,
    )


def get_user_manager() -> UserManager:
    """Get UserManager instance from dependency manager."""
    from botspot.core.dependency_manager import get_dependency_manager

    user_manager = get_dependency_manager().user_manager
    if user_manager is None:
        raise RuntimeError(
            "UserManager is not initialized. Make sure user_data component is enabled in settings."
        )
    return user_manager


def setup_dispatcher(dp: Dispatcher, **kwargs):
    """Setup the user data component"""
    settings = UserDataSettings(**kwargs)
    if not settings.enabled:
        return

    if settings.middleware_enabled:
        dp.message.middleware(UserTrackingMiddleware(cache_ttl=settings.cache_ttl))

    if settings.user_types_enabled:
        from botspot import commands_menu as bot_commands_menu
        from botspot.commands_menu import Visibility

        router = Router(name="user_data")
        router.message.filter(AdminFilter())  # Only admins can use these commands

        @bot_commands_menu.add_command("make_friend", visibility=Visibility.ADMIN_ONLY)
        @router.message(Command("make_friend"))
        async def make_friend_cmd(message: Message):
            """Make a user a friend (admin only command)"""
            if not message.reply_to_message:
                await message.answer("Reply to a user's message to make them a friend")
                return

            assert message.reply_to_message.from_user is not None
            user_id = message.reply_to_message.from_user.id
            # Direct access to dependency_manager to avoid circular imports
            from botspot.core.dependency_manager import get_dependency_manager

            user_manager = get_dependency_manager().user_manager

            if await user_manager.make_friend(user_id):
                await message.answer(f"User {user_id} is now a friend!")
            else:
                await message.answer("Failed to update user type")

        dp.include_router(router)

    async def sync_types():
        from botspot.core.dependency_manager import get_dependency_manager

        manager = get_dependency_manager().user_manager

        await manager.sync_user_types()

    dp.startup.register(sync_types)


if __name__ == "__main__":
    import asyncio

    from aiogram.types import User as AiogramUser

    async def main():
        # Create a sample user
        telegram_user = AiogramUser(
            id=12345, first_name="John", last_name="Doe", username="johndoe", is_bot=False
        )

        # Get user manager
        user_manager = get_user_manager()

        # Create a User object from Telegram user data
        user = User(
            user_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
        )

        # Add user to database
        await user_manager.add_user(user)

        # Retrieve user from database
        assert user is not None
        retrieved_user = await user_manager.get_user(user.user_id)
        assert retrieved_user is not None
        print(f"Retrieved user: {retrieved_user.full_name} (ID: {retrieved_user.user_id})")
        print(f"User type: {retrieved_user.user_type}")

    asyncio.run(main())
