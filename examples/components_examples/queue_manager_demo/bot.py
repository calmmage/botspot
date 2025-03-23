"""
Queue Manager Demo Bot

This bot demonstrates the basic usage of the Queue Manager component.
- Send any message to add it to your personal queue
- Reply to your message with "next" to get the next item from the queue
- Reply to your message with "random" to get a random item from the queue
- Use /queue_show to see all items in your queue
- Use /queue_clear to clear your queue
"""

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv

from botspot.core.bot_manager import BotManager
from botspot.core.botspot_settings import BotspotSettings
from botspot.utils.deps_getters import get_queue_manager

load_dotenv()

# Enable components
settings = BotspotSettings(
    mongo_database={"enabled": True, "database": "queue_manager_demo"},
    queue_manager={"enabled": True, "commands_visible": True},
    bot_commands_menu={"enabled": True},
)

# Setup logging
logging.basicConfig(level=logging.INFO)


async def start_command(message: Message):
    """Send welcome message when user starts the bot."""
    await message.answer(
        "Welcome to Queue Manager Demo Bot!\n\n"
        "- Send any message to add it to your queue\n"
        "- Reply with 'next' to get the next item\n"
        "- Reply with 'random' to get a random item\n"
        "- Use /queue_show to see all items\n"
        "- Use /queue_clear to clear your queue"
    )


async def custom_command(message: Message):
    """Custom command to demonstrate manual queue operations."""
    user_id = message.from_user.id if message.from_user else 0
    queue_manager = get_queue_manager()
    
    # Get user's queue
    queue = queue_manager.get_queue(f"custom_{user_id}")
    
    # Add 5 test items
    for i in range(1, 6):
        await queue.add_value(f"Test item {i}", priority=i)
    
    await message.answer("Added 5 test items to your custom queue!")


async def main():
    # Initialize bot and dispatcher
    bot = Bot(token=os.getenv("BOT_TOKEN", ""), parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    
    # Initialize BotManager with our settings
    bot_manager = BotManager(bot=bot, dispatcher=dp, **settings.model_dump())
    
    # Setup dispatcher with all enabled components
    bot_manager.setup_dispatcher(dp)
    
    # Register our custom command handlers
    dp.message.register(start_command, Command("start"))
    dp.message.register(custom_command, Command("test_queue"))
    
    # Start polling
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())