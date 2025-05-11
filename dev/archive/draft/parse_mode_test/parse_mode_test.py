import asyncio
import os

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv
from loguru import logger

load_dotenv()


async def test_parse_mode():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        raise ValueError("BOT_TOKEN environment variable is not set")

    CHAT_ID = os.getenv("TEST_CHAT_ID")
    if not CHAT_ID:
        raise ValueError("TEST_CHAT_ID environment variable is not set")

    CHAT_ID_INT = int(CHAT_ID)  # Convert to int for type safety

    # Initialize bot with default properties including HTML parse mode
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        # Test 1: Default parse mode (HTML)
        msg1 = await bot.send_message(CHAT_ID_INT, "Hello, <b>world</b>")
        logger.info("Test 1 (HTML) succeeded")

        # Test 2: Try to force None parse mode
        msg2 = await bot.send_message(CHAT_ID_INT, "Hello, <world>", parse_mode=None)
        logger.info("Test 2 (None) succeeded")

        # Test 2: Try to force None parse mode
        msg3 = await bot.send_message(CHAT_ID_INT, "Hello, <world>")
        logger.info("Test 3 (None) succeeded")
    except Exception as e:
        logger.error(f"Error: {e}")

    try:
        # Test 3: Empty string parse mode (workaround)
        msg3 = await bot.send_message(CHAT_ID_INT, "Hello, <world>", parse_mode="")
        logger.info("Test 3 (empty string) succeeded")
    except Exception as e:
        logger.error(f"Error: {e}")

    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(test_parse_mode())
