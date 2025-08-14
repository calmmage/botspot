from typing import TYPE_CHECKING, Optional, Union

from aiogram.types import User as AiogramUser
from pydantic import BaseModel

from botspot.utils.cache_utils import AsyncLRUCache
from botspot.utils.internal import get_logger

if TYPE_CHECKING:
    from botspot.components.data.user_data import User

logger = get_logger()


# used for user comparison
class UserRecord(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = None
    # first_name: Optional[str] = None
    # last_name: Optional[str] = None
    phone: Optional[str] = None


UserLike = Union[str, int, UserRecord, AiogramUser, "User"]


def to_user_record(user: UserLike) -> UserRecord:
    from botspot.components.data.user_data import User

    if isinstance(user, UserRecord):
        return user
    elif isinstance(user, AiogramUser):
        assert not isinstance(user, (str, int))
        return UserRecord(
            user_id=user.id,
            username=user.username,
            # first_name=user.first_name,
            # last_name=user.last_name,
        )
    elif isinstance(user, User):
        return UserRecord(
            user_id=user.user_id,
            username=user.username,
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
    """
    Synchronous comparison of users - uses basic user records.

    Args:
        user1: First user to compare
        user2: Second user to compare

    Returns:
        True if users match, False otherwise
    """
    user1 = to_user_record(user1)
    user2 = to_user_record(user2)
    return _compare_user_records(user1, user2)


async def compare_users_async(
    user1: UserLike,
    user2: UserLike,
):
    """
    Asynchronous comparison of users - uses enriched user records.

    Args:
        user1: First user to compare
        user2: Second user to compare

    Returns:
        True if users match, False otherwise
    """
    if isinstance(user1, (str, int)):
        user1 = await get_user_record_enriched(user1)
    else:
        user1 = to_user_record(user1)

    if isinstance(user2, (str, int)):
        user2 = await get_user_record_enriched(user2)
    else:
        user2 = to_user_record(user2)

    return _compare_user_records(user1, user2)


def _compare_user_records(user1: UserRecord, user2: UserRecord) -> bool:
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


# Use the AsyncLRUCache from cache_utils module


# Create a singleton instance of the cache
_user_record_cache = AsyncLRUCache(maxsize=100, ttl=300)  # 5-minute TTL


async def get_user_record_enriched(user_key: Union[str, int]) -> UserRecord:
    """
    Get enriched user record from user_key, attempting to fetch additional data from user_data component.
    This function is cached to avoid excessive DB lookups.

    Args:
        user_key: User identifier (ID, username, or phone number)

    Returns:
        UserRecord with available information
    """

    # Use our custom async cache
    async def _get_record():
        from botspot.core.dependency_manager import get_dependency_manager

        deps = get_dependency_manager()

        # Start with basic record
        if isinstance(user_key, int):
            record = UserRecord(user_id=user_key)
        elif isinstance(user_key, str):
            if user_key.startswith("+"):
                record = UserRecord(phone=user_key)
            elif user_key.isdigit():
                record = UserRecord(user_id=int(user_key))
            elif user_key.startswith("@"):
                record = UserRecord(username=user_key.lstrip("@"))
            else:
                record = UserRecord(username=user_key)
        else:
            raise ValueError(f"Invalid user_key type: {type(user_key)}")

        # If user_data component is not enabled, return basic record
        if not (deps.botspot_settings.user_data.enabled and deps.user_manager is not None):
            return record

        # Try to find user in database
        if record.user_id:
            user = await deps.user_manager.get_user(record.user_id)
        elif record.username:
            user = await deps.user_manager.find_user(username=record.username)
        elif record.phone:
            user = await deps.user_manager.find_user(phone=record.phone)
        else:
            return record

        # If found, enrich record
        if user:
            if not record.user_id:
                record.user_id = user.user_id
            if not record.username and user.username:
                record.username = user.username
            # Add phone if we implement it in User model
            # if not record.phone and user.phone:
            #     record.phone = user.phone

        return record
    result = await _user_record_cache.get_or_set(user_key, _get_record)
    assert isinstance(result, UserRecord)
    return result


def get_user_record(user_key: Union[str, int]) -> UserRecord:
    """
    Synchronous version of get_user_record - doesn't do data enrichment.

    Args:
        user_key: User identifier (ID, username, or phone number)

    Returns:
        Basic UserRecord
    """
    if isinstance(user_key, int):
        return UserRecord(user_id=user_key)

    if not isinstance(user_key, str):
        raise ValueError(f"Invalid user_key type: {type(user_key)}")

    from botspot.utils.deps_getters import get_simple_user_cache

    uc = get_simple_user_cache()
    assert uc is not None
    if user_key.startswith("+"):
        return UserRecord(phone=user_key)
    if user_key.isdigit():
        try:
            ur = uc.get_user(int(user_key))
            assert ur is not None
            return UserRecord(user_id=ur.user_id, username=ur.username)
        except:
            return UserRecord(user_id=int(user_key))
    if user_key.startswith("@"):
        try:
            ur = uc.get_user_by_username(user_key.lstrip("@"))
            assert ur is not None
            return UserRecord(username=ur.username, user_id=ur.user_id)
        except:
            return UserRecord(username=user_key.lstrip("@"))
    return UserRecord(username=user_key)


# admin only telegram filter
def is_admin(user: UserLike) -> bool:
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    return any([compare_users(user, admin) for admin in deps.botspot_settings.admins])


def is_friend(user: UserLike) -> bool:
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    return any([compare_users(user, friend) for friend in deps.botspot_settings.friends])
