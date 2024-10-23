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

from dev.draft.lib_files.components import error_handler, print_bot_url, bot_commands_menu
from dev.draft.lib_files.dependency_manager import DependencyManager
from dev.draft.lib_files.nbl_settings import NBLSettings

load_dotenv()
# Bot token can be obtained via https://t.me/BotFather
TOKEN = getenv("TELEGRAM_BOT_TOKEN")

dp = Dispatcher()


@bot_commands_menu.add_command("start")
@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """Send a welcome message when the command /start is issued"""
    await message.answer(f"Hello, {html.bold(message.from_user.full_name)}!")


@bot_commands_menu.add_command("error")
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


# ---------------------------------------
# region NBL CONTENT START HERE
# ---------------------------------------
deps = DependencyManager(nbl_settings=NBLSettings())
error_handler.setup_dispatcher(dp)
print_bot_url.setup_dispatcher(dp)
bot_commands_menu.setup_dispatcher(dp)


# todo: let's register our commands:
# /start - to start the bot
# /error - to raise an exception
# ---------------------------------------
# region NBL CONTENT END HERE
# ---------------------------------------


async def main() -> None:
    # Initialize Bot instance with default bot properties which will be passed to all API calls
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # And the run events dispatching
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
