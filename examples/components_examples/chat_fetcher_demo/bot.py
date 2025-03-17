import asyncio
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from dotenv import load_dotenv
from loguru import logger

import botspot

# Load environment variables
load_dotenv()

# Initialize bot and dispatcher
token = os.getenv("TELEGRAM_BOT_TOKEN")
if not token:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set in environment variables")

bot = Bot(token=token)
dp = Dispatcher()


class ChatStates(StatesGroup):
    waiting_for_chat = State()
    waiting_for_message_count = State()
    waiting_for_search_query = State()


@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Start command handler"""
    username = message.from_user.username or message.from_user.first_name
    await message.answer(
        f"Hello, {username}! I'm a Chat Fetcher demo bot.\n\n"
        "I can help you access your Telegram chats and messages using the Telethon API.\n\n"
        "Available commands:\n"
        "/setup_telethon - Set up Telethon client\n"
        "/check_telethon - Check if Telethon client is active\n"
        "/list_chats - List your recent chats\n"
        "/search_chat - Search for chats by name\n"
        "/fetch_messages - Fetch messages from a chat\n"
        "/search_messages - Search for messages in a chat\n"
        "/help - Show this help message"
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Help command handler"""
    await message.answer(
        "Chat Fetcher Demo Bot Help:\n\n"
        "This bot demonstrates the ChatFetcher component from Botspot.\n\n"
        "Steps to use this bot:\n"
        "1. Use /setup_telethon to authorize the bot to access your Telegram account\n"
        "2. Use /list_chats to see your available chats\n"
        "3. Try /fetch_messages to get messages from a specific chat\n"
        "4. Use /search_chat and /search_messages to find content\n\n"
        "Available commands:\n"
        "/setup_telethon - Set up Telethon client\n"
        "/check_telethon - Check if Telethon client is active\n"
        "/list_chats - List your recent chats\n"
        "/search_chat - Search for chats by name\n"
        "/fetch_messages - Fetch messages from a chat\n"
        "/search_messages - Search for messages in a chat\n"
        "/help - Show this help message"
    )


@dp.message(Command("fetch_messages"))
async def cmd_fetch_messages(message: Message, state: FSMContext):
    """Fetch messages from a specific chat"""
    # Check if user has Telethon client
    from botspot import get_telethon_manager

    try:
        telethon_manager = get_telethon_manager()
        client = await telethon_manager.get_client(message.from_user.id)
        if not client or not await client.is_user_authorized():
            await message.reply(
                "You need to set up Telethon client first. Use /setup_telethon command."
            )
            return
    except Exception as e:
        await message.reply(f"Error checking Telethon client: {str(e)}")
        return

    await message.reply(
        "Please enter chat ID or username to fetch messages from.\n"
        "You can use @username format or numeric chat ID."
    )
    await state.set_state(ChatStates.waiting_for_chat)


@dp.message(ChatStates.waiting_for_chat)
async def process_chat_id(message: Message, state: FSMContext):
    """Process chat ID input"""
    chat_input = message.text.strip()

    # Store chat input in state
    await state.update_data(chat_input=chat_input)

    await message.reply("How many messages do you want to fetch? (Enter a number between 1-50)")
    await state.set_state(ChatStates.waiting_for_message_count)


@dp.message(ChatStates.waiting_for_message_count)
async def process_message_count(message: Message, state: FSMContext):
    """Process message count input and fetch messages"""
    try:
        count = int(message.text.strip())
        if count < 1 or count > 50:
            await message.reply("Please enter a number between 1 and 50.")
            return
    except ValueError:
        await message.reply("Please enter a valid number.")
        return

    # Get chat input from state
    data = await state.get_data()
    chat_input = data.get("chat_input")

    # Reset state
    await state.clear()

    # Fetch messages
    try:
        # Determine if input is username or chat ID
        chat_id = chat_input
        if chat_input.startswith("@"):
            # This is a username, need to resolve
            # For simplicity, we'll ask user to provide chat ID directly in this demo
            await message.reply(
                "Username resolution not implemented in this demo. "
                "Please use numeric chat ID. You can find chat IDs using /list_chats command."
            )
            return
        else:
            try:
                chat_id = int(chat_input)
            except ValueError:
                await message.reply("Invalid chat ID format. Please provide a numeric chat ID.")
                return

        # Use ChatFetcher to get messages
        from botspot import get_chat_fetcher

        chat_fetcher = get_chat_fetcher()
        messages = await chat_fetcher.get_messages(
            chat_id=chat_id, user_id=message.from_user.id, limit=count
        )

        if not messages:
            await message.reply(f"No messages found in chat {chat_id}.")
            return

        # Format and send results
        result = f"Found {len(messages)} messages in chat {chat_id}:\n\n"
        for i, msg in enumerate(messages[:10], 1):  # Limit display to 10 messages
            date_str = msg.date.strftime("%Y-%m-%d %H:%M:%S")
            text = msg.text or "[No text]"
            if len(text) > 50:
                text = text[:47] + "..."

            result += f"{i}. [{date_str}] {text}\n"

        if len(messages) > 10:
            result += f"\n... and {len(messages) - 10} more messages."

        await message.reply(result)

    except Exception as e:
        logger.exception(f"Error fetching messages: {e}")
        await message.reply(f"Error fetching messages: {str(e)}")


@dp.message(Command("search_messages"))
async def cmd_search_messages(message: Message, state: FSMContext):
    """Search for messages in a specific chat"""
    # Check if user has Telethon client
    from botspot import get_telethon_manager

    try:
        telethon_manager = get_telethon_manager()
        client = await telethon_manager.get_client(message.from_user.id)
        if not client or not await client.is_user_authorized():
            await message.reply(
                "You need to set up Telethon client first. Use /setup_telethon command."
            )
            return
    except Exception as e:
        await message.reply(f"Error checking Telethon client: {str(e)}")
        return

    await message.reply(
        "Please enter chat ID to search messages in.\n" "You can use numeric chat ID."
    )
    await state.set_state(ChatStates.waiting_for_chat)


@dp.message(ChatStates.waiting_for_chat, F.text)
async def process_chat_for_search(message: Message, state: FSMContext):
    """Process chat ID input for message search"""
    try:
        chat_id = int(message.text.strip())
    except ValueError:
        await message.reply("Invalid chat ID format. Please provide a numeric chat ID.")
        return

    # Store chat ID in state
    await state.update_data(chat_id=chat_id)

    await message.reply("What text would you like to search for in messages?")
    await state.set_state(ChatStates.waiting_for_search_query)


@dp.message(ChatStates.waiting_for_search_query)
async def process_search_query(message: Message, state: FSMContext):
    """Process search query and search messages"""
    search_query = message.text.strip()

    # Get chat ID from state
    data = await state.get_data()
    chat_id = data.get("chat_id")

    # Reset state
    await state.clear()

    # Search messages
    try:
        # Use ChatFetcher to search messages
        from botspot import get_chat_fetcher

        chat_fetcher = get_chat_fetcher()
        messages = await chat_fetcher.find_messages(
            query=search_query, chat_id=chat_id, user_id=message.from_user.id, limit=10
        )

        if not messages:
            await message.reply(f"No messages found matching '{search_query}' in chat {chat_id}.")
            return

        # Format and send results
        result = f"Found {len(messages)} messages matching '{search_query}' in chat {chat_id}:\n\n"
        for i, msg in enumerate(messages, 1):
            date_str = msg.date.strftime("%Y-%m-%d %H:%M:%S")
            text = msg.text or "[No text]"
            if len(text) > 50:
                text = text[:47] + "..."

            result += f"{i}. [{date_str}] {text}\n"

        await message.reply(result)

    except Exception as e:
        logger.exception(f"Error searching messages: {e}")
        await message.reply(f"Error searching messages: {str(e)}")


async def main():
    """Main function to start the bot"""
    # Initialize Botspot
    bot_manager = botspot.core.bot_manager.BotManager(bot=bot, dispatcher=dp)

    # Setup Botspot components with the dispatcher
    bot_manager.setup_dispatcher(dp)

    # Start polling
    logger.info("Starting bot...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
