import asyncio
import logging
import sys
from os import getenv

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from dotenv import load_dotenv

from botspot.components.bot_commands_menu import add_command
from botspot.components.user_data import get_user_manager
from botspot.core.bot_manager import BotManager

load_dotenv()
TOKEN = getenv("TELEGRAM_BOT_TOKEN")

dp = Dispatcher()
bm = BotManager()


@add_command("start")
@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """
    This handler will be called automatically by middleware,
    which will create a new user record if needed
    """
    await message.answer(
        f"Hello, {html.bold(message.from_user.full_name)}!\n"
        f"Your data has been saved automatically.\n"
        f"Use /stats to see total users count."
    )


@add_command("stats", "Show bot statistics")
@dp.message(Command("stats"))
async def stats_command(message: Message) -> None:
    user_manager = get_user_manager()
    users = user_manager._collection

    total_users = await users.count_documents({})
    await message.answer(f"Bot Statistics:\n" f"Total registered users: {total_users}")


@add_command("me", "Show my user data")
@dp.message(Command("me"))
async def me_command(message: Message, user_data) -> None:
    """
    user_data is automatically injected by middleware
    """
    await message.answer(
        f"Your data:\n"
        f"ID: {user_data.user_id}\n"
        f"Username: {user_data.username}\n"
        f"First Name: {user_data.first_name}\n"
        f"Last Name: {user_data.last_name}\n"
        f"Registered: {user_data.created_at}\n"
        f"Last update: {user_data.updated_at}"
    )


async def main() -> None:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    bm.setup_dispatcher(dp)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
