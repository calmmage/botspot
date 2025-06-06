import traceback
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from pydantic_settings import BaseSettings

from botspot.utils.easter_eggs import get_easter_egg
from botspot.utils.internal import get_logger

logger = get_logger()


class ErrorHandlerSettings(BaseSettings):
    enabled: bool = True
    easter_eggs: bool = True
    developer_chat_id: int = 0

    class Config:
        env_prefix = "BOTSPOT_ERROR_HANDLER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


async def error_handler(event: types.ErrorEvent, bot: Bot):
    """
    log error to the logger
    also send a message to the user
    """
    from botspot.core.dependency_manager import get_dependency_manager
    from botspot.core.errors import BotspotError
    from botspot.utils.send_safe import answer_safe, send_safe

    deps = get_dependency_manager()
    settings = deps.botspot_settings.error_handling

    tb = traceback.format_exc()
    # cut redundant part of the traceback:
    tb = tb.split(
        """    return await wrapped()
           ^^^^^^^^^^^^^^^"""
    )[-1]

    logger.error(tb)

    user = None
    if event.update.message and event.update.message.from_user:
        user = event.update.message.from_user.username

    error_data = {
        "user": user,
        "timestamp": datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
        "error": str(event.exception),
        "traceback": tb,
    }

    # Check if it's a BotspotError
    error = event.exception
    if isinstance(error, BotspotError):
        if error.user_message:
            response = error.user_message
        else:
            response = "Oops, something went wrong :("

        if error.easter_eggs and settings.easter_eggs:
            response += f"\nHere, take this instead: \n{get_easter_egg()}"
    else:
        response = "Oops, something went wrong :("
        if settings.easter_eggs:
            response += f"\nHere, take this instead: \n{get_easter_egg()}"

    if event.update.message:
        await answer_safe(event.update.message, response)

    # send the report to the developer
    if settings.developer_chat_id and (not isinstance(error, BotspotError) or error.report_to_dev):
        logger.debug(f"Sending error report to the developer: {settings.developer_chat_id}")
        error_description = "Error processing message:"
        for k, v in error_data.items():
            if k == "traceback" and isinstance(error, BotspotError) and not error.include_traceback:
                continue
            error_description += f"\n{k}: {v}"
        # force parse_mode to None to avoid HTML tags issues in the message
        await send_safe(chat_id=settings.developer_chat_id, text=error_description)


def setup_dispatcher(dp: Dispatcher):  # settings: ErrorHandlerSettings = None
    from botspot.core.dependency_manager import get_dependency_manager

    # check required dependencies
    deps = get_dependency_manager()
    if not deps.botspot_settings:
        raise ValueError(
            "Dependency manager is missing botspot_settings - required for error handling"
        )

    dp.errors.register(error_handler)
