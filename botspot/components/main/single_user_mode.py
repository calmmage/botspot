from collections import defaultdict
from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram import Dispatcher
from aiogram.types import Message, TelegramObject, Update
from loguru import logger
from pydantic_settings import BaseSettings

from botspot.utils import compare_users, send_safe, to_user_record


class SingleUserModeSettings(BaseSettings):
    enabled: bool = False
    user: Optional[str] = None

    class Config:
        env_prefix = "BOTSPOT_SINGLE_USER_MODE_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


async def single_user_mode_middleware(
    handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
    event: Update,
    data: Dict[str, Any],
) -> Any:
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    settings = deps.botspot_settings.single_user_mode

    if (
        not hasattr(event, "message")
        or event.message is None
        or not isinstance(event.message, Message)
    ):
        # ignore event
        logger.debug(f"Event {type(event)} has no message attribute - ignoring")
        return
    message = event.message

    if not hasattr(message, "from_user"):
        # ignore event
        logger.debug(f"Event {type(message)} has no from_user attribute - ignoring")
        return

    user_record = to_user_record(message.from_user)

    if compare_users(user_record, settings.user):
        logger.debug(f"Single user mode: user {user_record} is allowed")
        return await handler(event, data)
    else:
        logger.debug(
            f"Single user mode: user {user_record} is not allowed (expected {settings.user})"
        )

        if not hasattr(single_user_mode_middleware, "warned"):
            single_user_mode_middleware.warned = defaultdict(bool)

        # Warn once per chat
        if message.chat:
            if not single_user_mode_middleware.warned[message.chat.id]:
                single_user_mode_middleware.warned[message.chat.id] = True
                await send_safe(
                    message.chat.id,
                    "This is a personal bot. You are not allowed to use this bot.\n"
                    "This warning will not be shown again.",
                )


def initialize(settings: SingleUserModeSettings):
    if settings.user is None:
        logger.info(
            "Single user mode is enabled, but user is not set. Taking the first admin instead."
        )

        if not deps.botspot_settings.admins:
            raise ValueError("No admins found in settings")

        if len(deps.botspot_settings.admins) > 1:
            logger.warning("More than one admin found in settings. Using the first one.")

        settings.user = str(deps.botspot_settings.admins[0])


def setup_dispatcher(dp: Dispatcher) -> None:
    logger.debug("Adding single user mode middleware")
    dp.update.middleware(single_user_mode_middleware)
