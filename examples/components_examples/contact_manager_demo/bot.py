import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv

from botspot.core.bot_manager import BotManager
from botspot.utils.deps_getters import get_contact_manager


# Configure logging
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()


async def main():
    # Initialize Bot and Dispatcher
    bot = Bot(token=os.getenv("BOT_TOKEN"), parse_mode=ParseMode.MARKDOWN)
    dp = Dispatcher()

    # Initialize BotManager with our bot and dispatcher
    manager = BotManager(bot=bot, dispatcher=dp)
    
    # Set up the dispatcher with all enabled components
    manager.setup_dispatcher(dp)
    
    # Add custom command handler (optional, Contact Manager already adds its own handlers)
    @dp.message(Command("contacts_help"))
    async def contacts_help_cmd(message: Message):
        help_text = """
📇 **Contact Manager Help**

This bot helps you manage your contacts. You can:

- `/add_contact [info]` - Add a new contact
  Example: `/add_contact John Doe, phone: 555-1234, email: john@example.com`

- `/find_contact [search]` - Find contacts
  Example: `/find_contact John`

- `/random_contact` - Get a random contact

You can also simply send a message with contact info, and I'll offer to save it!
        """
        await message.reply(help_text)
    
    # Start the bot
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())