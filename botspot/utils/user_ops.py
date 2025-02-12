from typing import Optional, Union

from aiogram.types import User
from loguru import logger
from pydantic import BaseModel


# used for user comparison
class UserRecord(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = None
    # first_name: Optional[str] = None
    # last_name: Optional[str] = None
    phone: Optional[str] = None


UserLike = Union[str, int, UserRecord, User]


def to_user_record(user: UserLike) -> UserRecord:
    if isinstance(user, UserRecord):
        return user
    if isinstance(user, User):
        return UserRecord(
            user_id=user.id,
            username=user.username,
            # first_name=user.first_name,
            # last_name=user.last_name,
        )
    if isinstance(user, str):
        return get_user_record(user)
    if isinstance(user, int):
        return UserRecord(user_id=user)
    raise ValueError(f"Invalid user type: {type(user)}")


def compare_users(
    user1: UserLike,
    user2: UserLike,
):
    user1 = to_user_record(user1)
    user2 = to_user_record(user2)
    return _compare_user_recordss(user1, user2)


def _compare_user_recordss(user1: UserRecord, user2: UserRecord) -> bool:
    if user1.user_id and user2.user_id and user1.user_id == user2.user_id:
        logger.debug("User IDs match")
        return True
    if (
        user1.username
        and user2.username
        and user1.username.lstrip("@") == user2.username.lstrip("@")
    ):
        logger.debug("User usernames match")
        return True
    if user1.phone and user2.phone and user1.phone == user2.phone:
        logger.debug("User phone numbers match")
        return True
    # disabled - unsafe.
    # if (
    #     user1.first_name == user2.first_name
    #     and user1.last_name == user2.last_name
    # ):
    #     return True
    return False


def get_user_record(user_key: str):
    if user_key.startswith("+"):
        return UserRecord(phone=user_key)
    elif user_key.startswith("@"):
        return UserRecord(username=user_key.lstrip("@"))
    else:
        return UserRecord(user_id=int(user_key))


# admin only telegram filter
def is_admin(user: UserLike) -> bool:
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    return any([compare_users(user, admin) for admin in deps.botspot_settings.admins])


def is_friend(user: UserLike) -> bool:
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    return any([compare_users(user, friend) for friend in deps.botspot_settings.friends])
