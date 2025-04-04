from typing import Any, Optional, Union

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message, User
from loguru import logger
from pydantic_settings import BaseSettings


class AdminFilterSettings(BaseSettings):
    notify_blocked: bool = True

    class Config:
        env_prefix = "BOTSPOT_ADMIN_FILTER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# todo consolidate this class and is_admin function to avoid responsibility duplication
class AdminFilter(BaseFilter):
    async def __call__(self, event: Union[Message, CallbackQuery], *args: Any) -> bool:
        from botspot import send_safe
        from botspot.core.dependency_manager import get_dependency_manager
        from botspot.utils import is_admin

        deps = get_dependency_manager()
        settings = deps.botspot_settings
        from_user: Optional[User] = event.from_user

        if not from_user:
            return False

        result = is_admin(from_user)

        if not result:
            logger.info(f"BLocking non-admin user: {from_user}, event: {event}")
            if settings.admin_filter.notify_blocked:
                await send_safe(from_user.id, "You are not an admin")

        return result
