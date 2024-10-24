from datetime import datetime
from typing import TYPE_CHECKING, Optional, Dict, Any

from aiogram import types
from aiogram.types import User as TelegramUser
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger

if TYPE_CHECKING:
    from pymongo.collection import Collection

logger = get_logger()


class UserDataSettings(BaseSettings):
    enabled: bool = True
    collection: str = "users"

    class Config:
        env_prefix = "NBL_USER_DATA_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class UserData(BaseModel):
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()
    settings: Dict[str, Any] = {}

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def from_telegram_user(cls, user: TelegramUser) -> "UserData":
        return cls(user_id=user.id, username=user.username, first_name=user.first_name, last_name=user.last_name)


class UserDataManager:
    def __init__(self):
        from botspot.components.mongo_database import get_db_manager
        from botspot.core.dependency_manager import get_dependency_manager

        deps = get_dependency_manager()
        settings = deps.nbl_settings.user_data

        db_manager = get_db_manager()
        if not db_manager:
            raise RuntimeError("MongoDB is required for UserData component")

        self._collection: Collection = db_manager.get_collection(settings.collection)

    async def get_user(self, user_id: int) -> Optional[UserData]:
        """Get user data from database"""
        user_dict = await self._collection.find_one({"user_id": user_id})
        if user_dict:
            return UserData(**user_dict)
        return None

    async def save_user(self, user: UserData) -> None:
        """Save user data to database"""
        user.updated_at = datetime.now()
        await self._collection.update_one({"user_id": user.user_id}, {"$set": user.dict()}, upsert=True)


class UserDataMiddleware:
    async def __call__(self, handler, event, data):
        if not isinstance(event, (types.Message, types.CallbackQuery)):
            return await handler(event, data)

        user = event.from_user
        if not user:
            return await handler(event, data)

        user_manager = get_user_manager()
        if not user_manager:
            return await handler(event, data)

        # Get or create user data
        user_data = await user_manager.get_user(user.id)
        if not user_data:
            user_data = UserData.from_telegram_user(user)
            await user_manager.save_user(user_data)

        # Add user data to handler data
        data["user_data"] = user_data

        return await handler(event, data)


def setup_dispatcher(dp):
    """Setup user data middleware"""
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    if not deps.nbl_settings.user_data.enabled:
        logger.info("UserData component is disabled")
        return dp

    try:
        deps.user_manager = UserDataManager()
        dp.message.middleware(UserDataMiddleware())
        dp.callback_query.middleware(UserDataMiddleware())
        logger.info("UserData middleware initialized")
    except Exception as e:
        logger.error(f"Failed to initialize UserData component: {e}")

    return dp


def get_user_manager() -> Optional[UserDataManager]:
    """Helper function to get user manager"""
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    return getattr(deps, "user_manager", None)
