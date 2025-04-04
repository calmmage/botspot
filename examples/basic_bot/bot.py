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
from botspot.core.bot_manager import BotManager

load_dotenv()
# Bot token can be obtained via https://t.me/BotFather
TOKEN = getenv("TELEGRAM_BOT_TOKEN")

dp = Dispatcher()


@add_command("start")
@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """Send a welcome message when the command /start is issued"""
    assert message.from_user is not None
    await message.answer(f"Hello, {html.bold(message.from_user.full_name)}!")


@add_command("error")
@dp.message(Command("error"))
async def command_error_handler(message: Message) -> None:
    """Raise an exception to test error handling"""
    raise Exception("Something Went Wrong")


@dp.message()
async def echo_handler(message: Message) -> None:
    try:
        # Send a copy of the received message
        await message.send_copy(chat_id=message.chat.id)
    except TypeError:
        # But not all the types is supported to be copied so need to handle it
        await message.answer("Nice try!")


bm = BotManager()
bm.setup_dispatcher(dp)


async def main() -> None:
    # Initialize Bot instance with default bot properties
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
