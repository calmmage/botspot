from enum import Enum
from typing import Optional, Union

from pydantic_settings import BaseSettings

from botspot.components.user_data import User
from botspot.utils.deps_getters import get_user_manager


class UserType(str, Enum):
    """User type enumeration"""

    REGULAR = "regular"
    FRIEND = "friend"
    ADMIN = "admin"


class CustomUser(User):
    """Extended user model with user type"""

    user_type: UserType = UserType.REGULAR


class AppConfig(BaseSettings):
    """Basic app configuration"""

    telegram_bot_token: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class App:
    name = "User Management Bot"

    def __init__(self, **kwargs):
        self.config = AppConfig(**kwargs)
        self._user_manager = None

    @property
    def user_manager(self) -> "UserManager":
        """Get user manager with custom user class"""
        if self._user_manager is None:
            self._user_manager = get_user_manager()
            # Override the user class to use our custom one
            self._user_manager.user_class = CustomUser
        return self._user_manager

    async def get_user(self, user_id: int) -> Optional[CustomUser]:
        """Get user by ID"""
        return await self.user_manager.get_user(user_id)

    async def set_user_type(self, user_id: int, user_type: UserType) -> bool:
        """Set user type for a user"""
        user = await self.get_user(user_id)
        if not user:
            return False

        user.user_type = user_type
        return await self.user_manager.add_user(user)

    async def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        user = await self.get_user(user_id)
        return bool(user and user.user_type == UserType.ADMIN)

    async def is_friend(self, user_id: int) -> bool:
        """Check if user is friend"""
        user = await self.get_user(user_id)
        return bool(user and user.user_type == UserType.FRIEND)

    async def get_user_stats(self) -> dict[str, Union[int, dict[UserType, int]]]:
        """Get user statistics"""
        # Get all users
        cursor = self.user_manager.db[self.user_manager.collection].find()

        # Initialize counters
        stats: dict[str, Union[int, dict[UserType, int]]] = {
            "total": 0,
            "by_type": {UserType.ADMIN: 0, UserType.FRIEND: 0, UserType.REGULAR: 0},
        }

        # Count users
        async for user_data in cursor:
            user = self.user_manager.user_class(**user_data)
            stats["total"] += 1
            stats["by_type"][user.user_class] += 1

        return stats
