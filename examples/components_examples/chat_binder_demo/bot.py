import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv

from botspot.components.new.chat_binder import bind_chat, get_bind_chat_id, get_user_bound_chats, unbind_chat
from botspot.core.bot_manager import BotManager


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize router
router = Router(name="chat_binder_demo")


@router.message(Command("start"))
async def start_handler(message: Message):
    await message.reply(
        "Welcome to Chat Binder Demo Bot!\n\n"
        "Available commands:\n"
        "/bind_chat [key] - Bind this chat to you (optional key)\n"
        "/unbind_chat [key] - Unbind this chat (optional key)\n"
        "/list_chats - List your bound chats\n"
        "/get_chat [key] - Get chat ID for specific key"
    )


@router.message(Command("list_chats"))
async def list_chats_handler(message: Message):
    if not message.from_user:
        await message.reply("User information is missing.")
        return
    
    try:
        bound_chats = await get_user_bound_chats(message.from_user.id)
        if not bound_chats:
            await message.reply("You don't have any bound chats.")
            return
        
        chats_info = "\n".join([f"Key: {chat.key}, Chat ID: {chat.chat_id}" for chat in bound_chats])
        await message.reply(f"Your bound chats:\n{chats_info}")
    except Exception as e:
        await message.reply(f"Error listing chats: {str(e)}")


@router.message(Command("get_chat"))
async def get_chat_handler(message: Message):
    if not message.from_user:
        await message.reply("User information is missing.")
        return
    
    key = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else "default"
    
    try:
        chat_id = await get_bind_chat_id(message.from_user.id, key)
        await message.reply(f"Bound chat for key '{key}': {chat_id}")
    except Exception as e:
        await message.reply(f"Error: {str(e)}")


async def main():
    # Load token from environment variable
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("BOT_TOKEN environment variable is not set.")
        return

    # Create bot and dispatcher
    bot = Bot(token=token)
    dp = Dispatcher()

    # Configure bot with required components
    bot_manager = BotManager(
        bot=bot,
        dispatcher=dp,
        mongo_database={"enabled": True, "uri": os.getenv("MONGO_URI", "mongodb://localhost:27017"), "db_name": "botspot_demo"},
        chat_binder={"enabled": True},
    )

    # Setup dispatcher
    bot_manager.setup_dispatcher(dp)
    
    # Include our router
    dp.include_router(router)

    # Start polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())