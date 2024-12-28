"""
Example usage of the telethon_manager component.
"""

import asyncio
import logging
import sys
from os import getenv

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from dotenv import load_dotenv

from botspot.core.bot_manager import BotManager

# Load environment variables
load_dotenv()

# Bot token can be obtained via https://t.me/BotFather
TOKEN = getenv("TELEGRAM_BOT_TOKEN")

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)


async def main() -> None:
    # Initialize Bot instance with a default parse mode
    bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher()

    # Initialize BotManager with telethon_manager enabled
    bm = BotManager(
        bot=bot,
        # Enable ask_user component as it's required for telethon_manager
        ask_user={"enabled": True},
        # Enable bot_commands_menu to register commands
        bot_commands_menu={"enabled": True},
    )

    # Setup dispatcher with components
    bm.setup_dispatcher(dp)

    # Start polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
