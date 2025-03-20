"""
Queue Manager Demo Bot

This bot demonstrates the Queue Manager component from Botspot.
It automatically queues all messages sent to it, and allows you to
retrieve items with /next and /random commands.
"""

import asyncio
import os
import sys

import aiogram.types

# import coloredlogs
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from calmlib.utils import setup_logger

from botspot.components.data.mongo_database import MongoDatabaseSettings
from botspot.components.data.mongo_database import initialize as init_mongo
from botspot.components.new.queue_manager import QueueManagerSettings, get_queue_manager
from botspot.components.new.queue_manager import initialize as init_queue_manager
from botspot.core.botspot_settings import BotspotSettings
from botspot.core.dependency_manager import DependencyManager

# Set up logging
logger = setup_logger()
# coloredlogs.install(level="DEBUG", logger=logger)


class QueueDemoSettings(BaseSettings):
    """Settings for the Queue Manager Demo Bot."""

    bot_token: str

    class Config:
        env_prefix = "BOTSPOT_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


async def setup():
    """Set up the bot, dependency manager, and components."""

    # Load environment variables
    load_dotenv()

    # Initialize settings
    botspot_settings = BotspotSettings()
    queue_demo_settings = QueueDemoSettings()
    mongo_settings = MongoDatabaseSettings()
    queue_manager_settings = QueueManagerSettings()

    # Create bot and dispatcher
    bot = Bot(token=queue_demo_settings.bot_token, parse_mode="HTML")
    dp = Dispatcher()

    # Initialize dependency manager
    deps = DependencyManager(botspot_settings=botspot_settings, bot=bot, dispatcher=dp)

    # Initialize MongoDB
    if mongo_settings.enabled:
        mongo_client, mongo_db = init_mongo(mongo_settings)
        deps.mongo_client = mongo_client
        deps.mongo_database = mongo_db
    else:
        logger.warning("MongoDB is disabled. Queue Manager requires MongoDB to function!")
        return None, None

    # Initialize Queue Manager
    if queue_manager_settings.enabled:
        queue_manager = init_queue_manager(queue_manager_settings)
        deps.queue_manager = queue_manager
    else:
        logger.warning("Queue Manager is disabled!")
        return None, None

    logger.info("Bot and components initialized successfully!")
    return bot, dp


@aiogram.types.router.Router.message(Command("start", "help"))
async def cmd_start(message: Message):
    """Handler for /start and /help commands."""
    await message.reply(
        "👋 Welcome to the Queue Manager Demo Bot!\n\n"
        "Any message you send will be automatically added to the queue.\n\n"
        "Available commands:\n"
        "/next - Get the next item from the queue\n"
        "/random - Get a random item from the queue\n"
        "/stats - Show queue statistics\n"
        "/clear - Clear the queue\n"
        "/help - Show this help message"
    )


@aiogram.types.router.Router.message(Command("next"))
async def cmd_next(message: Message):
    """Handler for /next command - gets the next item from the queue."""
    try:
        queue_manager = get_queue_manager()
        queue = queue_manager.get_queue()

        item_data, metadata = await queue.get_next_item()

        if item_data is None:
            await message.reply("Queue is empty! Send me some messages to add them to the queue.")
            return

        # Format metadata nicely
        added_time = metadata.created_at.strftime("%Y-%m-%d %H:%M:%S")
        added_by = f"by user {metadata.added_by}" if metadata.added_by else ""

        await message.reply(
            f"📥 <b>Next item from queue:</b>\n\n"
            f"{item_data}\n\n"
            f"<i>Added {added_time} {added_by}</i>\n"
            f"<i>Item ID: {metadata.item_id}</i>"
        )
    except Exception as e:
        logger.error(f"Error handling next command: {e}")
        await message.reply(f"Error retrieving next item: {e}")


@aiogram.types.router.Router.message(Command("random"))
async def cmd_random(message: Message):
    """Handler for /random command - gets a random item from the queue."""
    try:
        queue_manager = get_queue_manager()
        queue = queue_manager.get_queue()

        item_data, metadata = await queue.get_random_item()

        if item_data is None:
            await message.reply("Queue is empty! Send me some messages to add them to the queue.")
            return

        # Format metadata nicely
        added_time = metadata.created_at.strftime("%Y-%m-%d %H:%M:%S")
        added_by = f"by user {metadata.added_by}" if metadata.added_by else ""

        await message.reply(
            f"🎲 <b>Random item from queue:</b>\n\n"
            f"{item_data}\n\n"
            f"<i>Added {added_time} {added_by}</i>\n"
            f"<i>Item ID: {metadata.item_id}</i>"
        )
    except Exception as e:
        logger.error(f"Error handling random command: {e}")
        await message.reply(f"Error retrieving random item: {e}")


@aiogram.types.router.Router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Handler for /stats command - shows queue statistics."""
    try:
        queue_manager = get_queue_manager()
        queue = queue_manager.get_queue()

        stats = await queue.get_queue_stats()

        oldest = (
            stats.oldest_item_date.strftime("%Y-%m-%d %H:%M:%S")
            if stats.oldest_item_date
            else "N/A"
        )
        newest = (
            stats.newest_item_date.strftime("%Y-%m-%d %H:%M:%S")
            if stats.newest_item_date
            else "N/A"
        )

        await message.reply(
            f"📊 <b>Queue Statistics</b>\n\n"
            f"Queue: {stats.queue_key}\n"
            f"Total items: {stats.total_items}\n"
            f"Oldest item: {oldest}\n"
            f"Newest item: {newest}"
        )
    except Exception as e:
        logger.error(f"Error handling stats command: {e}")
        await message.reply(f"Error retrieving queue statistics: {e}")


@aiogram.types.router.Router.message(Command("clear"))
async def cmd_clear(message: Message):
    """Handler for /clear command - clears the queue."""
    try:
        queue_manager = get_queue_manager()
        queue = queue_manager.get_queue()

        count = await queue.clear()

        await message.reply(f"🗑 Queue cleared! Removed {count} items.")
    except Exception as e:
        logger.error(f"Error handling clear command: {e}")
        await message.reply(f"Error clearing queue: {e}")


@aiogram.types.router.Router.message(F.text)
async def on_message(message: Message):
    """Handler for all text messages - adds them to the queue."""
    try:
        queue_manager = get_queue_manager()
        queue = queue_manager.get_queue()

        # Add the message text to the queue
        item_id = await queue.add_item(message.text, added_by=message.from_user.id)

        await message.reply(
            f"✅ Added to queue with ID: {item_id}\n\n"
            f"Use /next to get the next item or /random to get a random item."
        )
    except Exception as e:
        logger.error(f"Error adding message to queue: {e}")
        await message.reply(f"Error adding message to queue: {e}")


async def main():
    """Main function to run the bot."""

    # Set up the bot and components
    bot, dp = await setup()

    if bot is None or dp is None:
        logger.error("Failed to initialize bot or components")
        return

    # Register command handlers
    dp.message.register(cmd_start, Command("start", "help"))
    dp.message.register(cmd_next, Command("next"))
    dp.message.register(cmd_random, Command("random"))
    dp.message.register(cmd_stats, Command("stats"))
    dp.message.register(cmd_clear, Command("clear"))
    dp.message.register(on_message, F.text)

    # Start the bot
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
    except Exception as e:
        logger.exception(f"Error running bot: {e}")
