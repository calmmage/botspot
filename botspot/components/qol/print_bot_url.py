from aiogram import Bot, Dispatcher
from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger

logger = get_logger()


class PrintBotUrlSettings(BaseSettings):
    enabled: bool = True

    class Config:
        env_prefix = "BOTSPOT_PRINT_BOT_URL_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


async def print_bot_url(bot: Bot):
    bot_info = await bot.get_me()
    logger.info(f"Bot url: https://t.me/{bot_info.username}")


def setup_dispatcher(dp: Dispatcher):
    dp.startup.register(print_bot_url)
