from typing import TYPE_CHECKING, Optional, Union

from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.types import User as AiogramUser
from botspot.utils.cache_utils import AsyncLRUCache
from botspot.utils.internal import get_logger
from pydantic import BaseModel

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


async def get_username_from_message(
    chat_id: int,
    state: FSMContext,  # type: ignore
    prompt: str = "Please send the username or forward a message from that user:",
    cleanup: bool = False,
    timeout: Optional[int] = None,
    max_retries: int = 3,
) -> Optional[str]:
    """
    Get username from user with multiple input methods.

    Supports:
    1. Text message with @username, username, or user ID
    2. Forwarded message (extracts from forward_from)
    3. Retry logic for invalid inputs

    Args:
        chat_id: Chat ID to send prompt to
        state: FSM context for state management
        prompt: Prompt message to show user
        cleanup: Whether to cleanup messages after interaction
        timeout: Timeout in seconds (None for no timeout)
        max_retries: Maximum number of retry attempts

    Returns:
        Username (with @ prefix for usernames, plain for user IDs) or None if failed

    Examples:
        >>> # username = await get_username_from_message(chat_id, state)
        >>> # User can:
        >>> # 1. Send: "@john" or "john" or "123456789"
        >>> # 2. Forward a message from john
        >>> # Result: "@john" or "123456789"
    """
    from aiogram.types import Message
    from botspot.components.features.user_interactions import ask_user_raw

    for attempt in range(max_retries):
        # Ask user for username or forward
        logger.info(
            f"Asking for username (attempt {attempt + 1}/{max_retries})..."
        )
        response_message: Optional[Message] = await ask_user_raw(
            chat_id=chat_id,
            question=prompt,
            state=state,
            cleanup=cleanup,
            timeout=timeout,
        )

        if response_message is None:
            logger.warning("No response received from user")
            return None

        # Try to extract username from response
        username = _extract_username_from_message(response_message)

        if username:
            logger.info(f"Successfully extracted username: {username}")
            return username

        # Failed to extract, retry with more specific prompt
        if attempt < max_retries - 1:
            prompt = (
                "❌ Could not extract username. Please try again:\n"
                "- Send username: @john or john\n"
                "- Send user ID: 123456789\n"
                "- Forward a message from that user"
            )
        else:
            logger.warning(
                f"Failed to extract username after {max_retries} attempts"
            )
            return None

    return None


def _extract_username_from_message(message: Message) -> Optional[str]:  # type: ignore
    """
    Extract username from a message.

    Supports:
    1. Forwarded message -> extract from forward_from
    2. Text message -> parse @username, username, or user ID

    Args:
        message: Message to extract username from

    Returns:
        Username with @ prefix (for usernames) or plain (for user IDs), or None if failed
    """

    # Method 1: Extract from forwarded message
    if message.forward_from:
        # Message forwarded from a user
        user = message.forward_from

        if user.username:
            username = f"@{user.username}"
            logger.info(
                f"Extracted username from forwarded message: {username}"
            )
            return username
        elif user.id:
            # No username, use user ID
            user_id = str(user.id)
            logger.info(
                f"Extracted user ID from forwarded message: {user_id}"
            )
            return user_id
        else:
            logger.warning(
                "Forwarded message from user without username or ID"
            )
            return None

    # Method 2: Extract from text message
    if message.text:
        text = message.text.strip()

        # Check if it's a valid username or user ID
        if text.startswith("@"):
            # Username with @ prefix
            username = text
            logger.info(f"Extracted username from text: {username}")
            return username
        elif text.isdigit():
            # User ID
            user_id = text
            logger.info(f"Extracted user ID from text: {user_id}")
            return user_id
        else:
            # Username without @ prefix
            username = f"@{text}"
            logger.info(
                f"Extracted username from text (added @ prefix): {username}"
            )
            return username

    logger.warning("Could not extract username from message")
    return None


async def get_username_from_command_or_dialog(
    message: Message,  # type: ignore
    state: FSMContext,  # type: ignore
    cleanup: bool = False,
    prompt: str = "Please send the username or forward a message from that user:",
    timeout: Optional[int] = None,
) -> Optional[str]:
    """
    Get username either from command arguments or via interactive dialog.

    First tries to extract from command text (e.g., /add_friend @john),
    if not found, asks user interactively.

    Args:
        message: Original command message
        state: FSM context
        cleanup: Whether to cleanup messages
        prompt: Prompt for interactive dialog
        timeout: Timeout for interactive dialog

    Returns:
        Username or None if failed
    """

    # Try to get from command arguments first
    if message.text:
        parts = message.text.split(maxsplit=1)
        if len(parts) >= 2:
            # Username provided in command
            username_text = parts[1].strip()

            # Normalize
            if username_text.startswith("@"):
                return username_text
            elif username_text.isdigit():
                return username_text
            else:
                return f"@{username_text}"

    # No username in command, ask interactively
    logger.info("No username in command, asking user interactively")
    return await get_username_from_message(
        chat_id=message.chat.id,
        state=state,
        prompt=prompt,
        cleanup=cleanup,
        timeout=timeout,
    )
