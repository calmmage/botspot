import asyncio
import logging
import sys
from os import getenv

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from dotenv import load_dotenv

from botspot.commands_menu import add_command
from botspot.components.trial_mode import add_global_limit, add_user_limit
from botspot.core.bot_manager import BotManager

load_dotenv()
# Bot token can be obtained via https://t.me/BotFather
TOKEN = getenv("TELEGRAM_BOT_TOKEN")

dp = Dispatcher()
bm = BotManager()


@add_command("start")
@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """Send a welcome message when the command /start is issued"""
    await message.answer(
        f"Hello, {html.bold(message.from_user.full_name)}! Welcome to the Trial Mode Demo Bot."
    )


@add_command("limited_user")
@dp.message(Command("limited_user"))
@add_user_limit(limit=3, period=60)  # Limit to 3 uses per minute per user
async def limited_user_command(message: Message) -> None:
    """A command with a per-user usage limit"""
    await message.answer(
        "You've used the limited_user command. It has a per-user limit of 3 uses per minute."
    )


@add_command("limited_global")
@dp.message(Command("limited_global"))
@add_global_limit(limit=5, period=60)  # Limit to 5 uses per minute globally
async def limited_global_command(message: Message) -> None:
    """A command with a global usage limit"""
    await message.answer(
        "You've used the limited_global command. It has a global limit of 5 uses per minute."
    )


@add_command("unlimited")
@dp.message(Command("unlimited"))
async def unlimited_command(message: Message) -> None:
    """A command without any usage limits"""
    await message.answer("This command has no usage limits.")


@dp.message()
async def echo_handler(message: Message) -> None:
    """Echo any other message"""
    await message.answer("This is an echo message. It's subject to the global middleware limits.")


async def main() -> None:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    bm.setup_dispatcher(dp)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
