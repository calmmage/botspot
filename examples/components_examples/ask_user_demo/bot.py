import asyncio
import logging
import sys
from os import getenv

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv

from botspot.components.ask_user_handler import ask_user
from botspot.components.bot_commands_menu import add_command
from botspot.core.bot_manager import BotManager

load_dotenv()
TOKEN = getenv("TELEGRAM_BOT_TOKEN")

dp = Dispatcher()
bm = BotManager()


@add_command("demo", "Demo command showcasing ask_user functionality")
@dp.message(Command("demo"))
async def demo_command(message: Message, state) -> None:
    """Simple demo of asking user for their name"""
    response = await ask_user(message, "What's your name?", state)
    await message.answer(f"Hello, {response}! Nice to meet you!")


async def main() -> None:
    bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
    bm.setup_dispatcher(dp)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
