import asyncio
import logging
import sys
from os import getenv

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv

from botspot.commands_menu import add_command
from botspot.core.bot_manager import BotManager
from botspot.user_interactions import ask_user, ask_user_choice

load_dotenv()
TOKEN = getenv("TELEGRAM_BOT_TOKEN")

dp = Dispatcher()


@add_command("demo", "Demo command showcasing ask_user functionality")
@dp.message(Command("demo"))
async def demo_command(message: Message, state) -> None:
    """Simple demo of asking user for their name"""
    response = await ask_user(message.chat.id, "What's your name?", state, timeout=30.0)
    if response:
        await message.reply(f"Hello, {response}! Nice to meet you!")
    else:
        await message.reply("Demo cancelled due to timeout.")


@add_command("choose", "Demo command showcasing button choices")
@dp.message(Command("choose"))
async def choose_command(message: Message, state) -> None:
    """Demo of asking user to choose from options"""
    choices = ["Red", "Green", "Blue"]
    response = await ask_user_choice(
        message.chat.id, "What's your favorite color?", choices, state, timeout=30.0
    )
    if response:
        await message.reply(f"You chose: {response}!")
    else:
        await message.reply("No color was chosen.")


async def main() -> None:
    # Create bot as usual in aiogram
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # Initialize BotManager with existing bot
    bm = BotManager(bot=bot)

    # Setup dispatcher with our components
    bm.setup_dispatcher(dp)

    # Start polling as usual
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
