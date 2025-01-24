from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message, User
from typing import Any, Optional, Union


class AdminFilter(BaseFilter):
    async def __call__(self, event: Union[Message, CallbackQuery], *args: Any) -> bool:
        from botspot.core.dependency_manager import get_dependency_manager

        deps = get_dependency_manager()
        from_user: Optional[User] = event.from_user

        if not from_user:
            return False

        return from_user.id in deps.botspot_settings.admins
