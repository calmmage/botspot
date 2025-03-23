"""
Context Builder Demo

This example demonstrates how to use the context builder component to bundle multiple
messages sent within a short time period.
"""

import asyncio
import os
from typing import Dict, Any

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv
from loguru import logger

from botspot.core.bot_manager import BotManager
from botspot.utils.deps_getters import get_context_builder

# Load environment variables
load_dotenv()


# Initialize router
router = Router()


@router.message(Command("start"))
async def start_handler(message: Message) -> None:
    """Handle the /start command."""
    await message.answer(
        "Welcome to the Context Builder Demo!\n\n"
        "Forward multiple messages to me within a short time frame, "
        "and I'll bundle them together and show you the combined context.\n\n"
        "You can also try sending multiple messages with text and media."
    )


@router.message(F.text | F.photo | F.video | F.document | F.audio | F.voice)
async def message_handler(message: Message, context_text: str = None, **data) -> None:
    """Handle incoming messages and demonstrate context building."""
    # If we have a context_text, it means we've received a complete bundle
    if context_text:
        # Wait a moment to make sure we've processed all messages in the bundle
        await asyncio.sleep(0.1)
        
        # Respond with the combined context
        await message.answer(
            f"I received a bundle of messages!\n\n"
            f"Here's the combined context:\n\n"
            f"{context_text}",
            parse_mode=ParseMode.HTML
        )
    else:
        # This message wasn't part of a completed bundle
        # We'll just acknowledge it was received
        await message.answer("Message received! If you send multiple messages quickly, I'll bundle them together.")


async def main() -> None:
    """Initialize and start the bot."""
    # Get the bot token from environment variables
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise ValueError("BOT_TOKEN environment variable is not set")

    # Create the bot instance
    bot = Bot(token=bot_token)
    dp = Dispatcher()

    # Initialize BotManager with context_builder enabled
    bot_manager = BotManager(bot=bot, dispatcher=dp)

    # Set up the dispatcher with all components
    bot_manager.setup_dispatcher(dp)

    # Include our router
    dp.include_router(router)

    # Log info about the context builder
    context_builder = get_context_builder()
    logger.info(f"Context Builder is enabled with bundle timeout: {context_builder.settings.bundle_timeout}s")

    # Start polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())