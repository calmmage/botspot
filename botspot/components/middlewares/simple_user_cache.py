from typing import Optional, Any, Awaitable, Callable, Dict
from pydantic import BaseModel

from aiogram.types import Update, Message


class SimpleUserRecord(BaseModel):
    username: str
    user_id: int
    # phone: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]


class SimpleUserCache:
    def __init__(self):
        self.cache = {}

    def get_user(self, user_id: int) -> Optional[SimpleUserRecord]:
        return self.cache.get(user_id)

    def get_user_by_username(self, username: str) -> Optional[SimpleUserRecord]:
        for user_record in self.cache.values():
            if user_record.username == username:
                return user_record
        return None

    # def get_user_by_phone(self, phone: str) -> Optional[SimpleUserRecord]:
    #     for user_record in self.cache.values():
    #         if user_record.phone == phone:
    #             return user_record
    #     return None

    def find_user(self, name: str) -> list[SimpleUserRecord]:
        candidates = []
        for user_record in self.cache.values():
            if name == user_record.first_name + " " + user_record.last_name:
                return [user_record]
            if name in (user_record.first_name + " " + user_record.last_name):
                candidates.append(user_record)
        return candidates

    def add_user(self, user_record: SimpleUserRecord):
        self.cache[user_record.user_id] = user_record

    def has_user(self, user_id: int) -> bool:
        return user_id in self.cache


async def simple_user_cache_middleware(
    handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]], event: Update, data: Dict[str, Any]
) -> Any:
    try:
        message = None
        if isinstance(event, Message) and event.from_user:
            message = event
        elif hasattr(event, "message") and event.message.from_user:
            message = event.message
        if message:
            suc = get_simple_user_cache()
            if not suc.has_user(message.from_user.id):
                user_record = SimpleUserRecord(
                    username=message.from_user.username,
                    user_id=message.from_user.id,
                    # phone=message.from_user.phone,
                    first_name=message.from_user.first_name,
                    last_name=message.from_user.last_name,
                )
                suc.add_user(user_record)
    except:
        # Handle the exception if needed
        pass
    return await handler(event, data)


def setup_dispatcher(dp):
    dp.update.middleware(simple_user_cache_middleware)


def initialize():
    return SimpleUserCache()


def get_simple_user_cache():
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    return deps.simple_user_cache
