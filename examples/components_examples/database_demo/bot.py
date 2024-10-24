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
from pydantic import BaseModel

from botspot.components.bot_commands_menu import add_command
from botspot.components.mongo_database import get_db_manager
from botspot.core.bot_manager import BotManager

load_dotenv()
TOKEN = getenv("TELEGRAM_BOT_TOKEN")

dp = Dispatcher()
bm = BotManager()


class Item(BaseModel):
    name: str
    description: str


@add_command("start")
@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer(
        f"Hello, {html.bold(message.from_user.full_name)}!\n"
        f"This bot demonstrates MongoDB integration.\n"
        f"Available commands:\n"
        f"/add_item <name> <description>\n"
        f"/get_item <name>\n"
        f"/list_items"
    )


@add_command("add_item", "Add new item to database")
@dp.message(Command("add_item"))
async def add_item(message: Message) -> None:
    try:
        _, name, *description_parts = message.text.split()
        description = " ".join(description_parts)

        db = get_db_manager()
        items = db.get_collection("items")

        item = Item(name=name, description=description)
        await items.update_one({"name": name}, {"$set": item.dict()}, upsert=True)

        await message.answer(f"Item '{name}' added successfully!")
    except ValueError:
        await message.answer("Usage: /add_item <name> <description>")


@add_command("get_item", "Get item by name")
@dp.message(Command("get_item"))
async def get_item(message: Message) -> None:
    try:
        _, name = message.text.split()

        db = get_db_manager()
        items = db.get_collection("items")

        item = await items.find_one({"name": name})
        if item:
            await message.answer(f"Name: {item['name']}\nDescription: {item['description']}")
        else:
            await message.answer(f"Item '{name}' not found")
    except ValueError:
        await message.answer("Usage: /get_item <name>")


@add_command("list_items", "List all items")
@dp.message(Command("list_items"))
async def list_items(message: Message) -> None:
    db = get_db_manager()
    items = db.get_collection("items")

    items_list = await items.find().to_list(length=None)
    if not items_list:
        await message.answer("No items found")
        return

    response = "Items in database:\n\n"
    for item in items_list:
        response += f"• {item['name']}: {item['description']}\n"

    await message.answer(response)


async def main() -> None:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    bm.setup_dispatcher(dp)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
