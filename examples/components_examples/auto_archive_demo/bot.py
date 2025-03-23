"""
Auto Archive Component Demo.

Shows how to use the AutoArchive component to forward messages to an archive chat and delete them 
from the original conversation.

Usage:
1. Create a new bot using @BotFather on Telegram
2. Install requirements: `pip install -e .`
3. Set up environment variables in .env file (see sample.env)
4. Run the bot: `python bot.py`
5. Send /bind_archive [chat_id] to bind an archive chat
6. Send any message to the bot, and it will be forwarded to the archive chat and deleted
"""

import asyncio
import os
from typing import Dict

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv
from loguru import logger

from botspot.core.bot_manager import BotManager


async def main_menu_handler(message: types.Message):
    """Handle /start command."""
    commands = [
        "/bind_archive [chat_id] - Bind current chat to archive chat",
        "/unbind_archive - Unbind current chat from archive",
        "/toggle_archive - Temporarily enable/disable archiving",
    ]
    await message.answer("Auto Archive Demo Bot\n\nAvailable commands:\n" + "\n".join(commands))


async def on_startup(bot: Bot, dispatcher: Dispatcher):
    """Print bot information on startup."""
    bot_info = await bot.get_me()
    logger.info(f"Bot started: @{bot_info.username}")
    print(f"Bot started! Open Telegram and message @{bot_info.username}")


async def main():
    """Start the bot."""
    # Load environment variables from .env file
    if os.path.exists(".env"):
        load_dotenv()
    else:
        logger.warning("No .env file found, using environment variables")

    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_TOKEN environment variable is not set")

    # Create bot and dispatcher instances
    bot = Bot(token=token)
    dp = Dispatcher()

    # Configure bot manager with required components
    manager = BotManager(
        bot=bot,
        dispatcher=dp,
        BOTSPOT_MONGO_DATABASE_ENABLED="true",
        BOTSPOT_MONGO_DATABASE_CONNECTION_STRING=os.getenv("MONGODB_CONNECTION_STRING", "mongodb://localhost:27017"),
        BOTSPOT_MONGO_DATABASE_NAME=os.getenv("MONGODB_DATABASE", "botspot_demo"),
        BOTSPOT_AUTO_ARCHIVE_ENABLED="true",
        BOTSPOT_AUTO_ARCHIVE_DELETE_DELAY="3",  # 3 seconds delay before deletion
    )

    # Setup dispatcher with components
    dp = manager.setup_dispatcher(dp)

    # Add main menu handler
    dp.message.register(main_menu_handler, Command("start", "help"))

    # Start the bot
    dp.startup.register(on_startup)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())