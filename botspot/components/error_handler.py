import traceback
from datetime import datetime

from aiogram import types, Dispatcher, Bot
from pydantic_settings import BaseSettings

from botspot.utils.common import get_logger
from botspot.utils.easter_eggs.main import get_easter_egg

logger = get_logger()


class ErrorHandlerSettings(BaseSettings):
    enabled: bool = True
    easter_eggs: bool = True
    developer_chat_id: int = 0

    class Config:
        env_prefix = "NBL_ERROR_HANDLER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


async def error_handler(event: types.ErrorEvent, bot: Bot):
    """
    log error to the logger
    also send a message to the user
    """
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    settings = deps.nbl_settings.error_handling

    tb = traceback.format_exc()
    # cut redundant part of the traceback:
    tb = tb.split(
        """    return await wrapped()
           ^^^^^^^^^^^^^^^"""
    )[-1]
    error_data = {
        "user": event.update.message.from_user.username,
        "timestamp": datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
        "error": str(event.exception),
        "traceback": tb,
    }

    logger.error(tb)

    if event.update.message:
        response = "Oops, something went wrong :("
        if settings.easter_eggs:
            response += f"\nHere, take this instead: \n{get_easter_egg()}"

        await event.update.message.answer(response)

    # send the report to the developer
    if settings.developer_chat_id:
        logger.debug(f"Sending error report to the developer: {settings.developer_chat_id}")
        error_description = f"Error processing message:"
        for k, v in error_data.items():
            error_description += f"\n{k}: {v}"
        await bot.send_message(chat_id=settings.developer_chat_id, text=error_description)


def setup_dispatcher(dp: Dispatcher):  # settings: ErrorHandlerSettings = None
    from botspot.core.dependency_manager import get_dependency_manager

    # check required dependencies
    deps = get_dependency_manager()
    if not deps.nbl_settings:
        raise ValueError("Dependency manager is missing nbl_settings - required for error handling")

    # if not deps.nbl_settings.error_handling.enabled:
    #     logger.info("Error handling is disabled - skipping setup")
    dp.errors.register(error_handler)
