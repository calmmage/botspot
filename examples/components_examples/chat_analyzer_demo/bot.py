import asyncio
import os
from datetime import datetime

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


@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Start command handler"""
    username = message.from_user.username or message.from_user.first_name
    await message.answer(
        f"Hello, {username}! I'm a Chat Analyzer bot.\n\n"
        "I can help you analyze Telegram chats by first ingesting messages "
        "and then providing statistics from the cached data.\n\n"
        "Available commands:\n"
        "/setup_telethon - Set up Telethon client\n"
        "/ingest - Ingest messages from a specific chat\n"
        "/stats - Show statistics about ingested chats\n"
        "/help - Show this help message"
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Help command handler"""
    await message.answer(
        "Chat Analyzer Bot Help:\n\n"
        "This bot demonstrates the ChatFetcher component with message caching.\n\n"
        "Steps to use this bot:\n"
        "1. Use /setup_telethon to authorize the bot to access your Telegram account\n"
        "2. Use /ingest to load messages from a specific chat into the cache\n"
        "3. Use /stats to view statistics about cached chats and messages\n\n"
        "Available commands:\n"
        "/setup_telethon - Set up Telethon client\n"
        "/ingest - Ingest messages from a specific chat\n"
        "/stats - Show statistics about ingested chats and messages\n"
        "/help - Show this help message"
    )


@dp.message(Command("ingest"))
async def cmd_ingest(message: Message, state: FSMContext):
    """Command to ingest messages from a chat and store them in MongoDB"""
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

    # Check if command has a chat_id parameter
    parts = message.text.split(maxsplit=1)
    if len(parts) > 1:
        # Use provided chat_id
        try:
            chat_id = int(parts[1])
            await ingest_chat(message, chat_id)
        except ValueError:
            await message.reply(
                "Invalid chat ID format. Please provide a numeric chat ID or use /ingest without parameters to enter interactive mode."
            )
    else:
        # Ask user for chat ID
        await message.reply(
            "Please enter chat ID to ingest messages from.\n"
            "You can use numeric chat ID or use /list_chats to see available chats."
        )
        await state.set_state(ChatStates.waiting_for_chat)


@dp.message(ChatStates.waiting_for_chat)
async def process_chat_for_ingestion(message: Message, state: FSMContext):
    """Process chat ID input for message ingestion"""
    await state.clear()
    
    try:
        chat_id = int(message.text.strip())
        await ingest_chat(message, chat_id)
    except ValueError:
        await message.reply("Invalid chat ID format. Please provide a numeric chat ID.")


async def ingest_chat(message: Message, chat_id: int):
    """Ingest messages from the specified chat"""
    try:
        # Use ChatFetcher to download messages
        from botspot import get_chat_fetcher

        chat_fetcher = get_chat_fetcher()
        
        # Send initial response
        status_message = await message.reply(
            f"Starting ingestion of messages from chat {chat_id}...\n"
            "This may take a few minutes depending on chat size."
        )
        
        # Use load_chat_history to efficiently fetch and cache messages
        messages = await chat_fetcher.load_chat_history(
            chat_id=chat_id, 
            user_id=message.from_user.id,
            # The method automatically checks the cache first and only fetches new messages
        )
        
        # Send completion message
        if messages:
            min_date = min(msg.date for msg in messages).strftime("%d %b %Y")
            max_date = max(msg.date for msg in messages).strftime("%d %b %Y")
            
            await status_message.edit_text(
                f"✅ Successfully ingested {len(messages)} messages from chat {chat_id}.\n\n"
                f"Date range: {min_date} - {max_date}\n\n"
                "Use /stats to see information about the cached messages."
            )
        else:
            await status_message.edit_text(
                f"No messages found in chat {chat_id} or ingestion was skipped."
            )
            
    except Exception as e:
        logger.exception(f"Error in ingest_chat: {e}")
        await message.reply(f"Error ingesting chat: {str(e)}")


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    """Show statistics about ingested chats and messages"""
    try:
        # Use ChatFetcher to get statistics from the cache
        from botspot import get_chat_fetcher, get_dependency_manager

        chat_fetcher = get_chat_fetcher()
        deps = get_dependency_manager()
        
        if not deps.mongo_database or not chat_fetcher.messages_collection:
            await message.reply("MongoDB cache is not available. Make sure it's properly configured.")
            return
        
        # Get message count from MongoDB
        message_count = await chat_fetcher.messages_collection.count_documents({})
        
        if message_count == 0:
            await message.reply(
                "No messages found in the cache. Use /ingest to load messages first."
            )
            return
        
        # Get distinct chat count
        chats = await chat_fetcher.messages_collection.distinct("chat_id")
        chat_count = len(chats)
        
        # Get latest message from each chat (up to 5 chats)
        stats_text = f"📊 Chat Statistics\n\n"
        stats_text += f"Total messages in cache: {message_count}\n"
        stats_text += f"Total chats in cache: {chat_count}\n\n"
        
        # For each chat, show message count and latest message
        for i, chat_id in enumerate(chats[:5]):  # Limit to first 5 chats
            # Get count of messages for this chat
            chat_message_count = await chat_fetcher.messages_collection.count_documents({"chat_id": chat_id})
            
            # Get latest message
            latest_message = await chat_fetcher.messages_collection.find_one(
                {"chat_id": chat_id},
                sort=[("date", -1)]
            )
            
            if latest_message:
                # Try to get chat name
                chat_obj = await chat_fetcher.chats_collection.find_one({"id": chat_id})
                chat_name = chat_obj["title"] if chat_obj else f"Chat {chat_id}"
                
                # Format the message text
                message_text = latest_message.get("text", "[No text]")
                if message_text and len(message_text) > 50:
                    message_text = message_text[:47] + "..."
                
                # Format date
                date_str = datetime.fromisoformat(str(latest_message["date"])).strftime("%Y-%m-%d %H:%M")
                
                stats_text += f"Chat: {chat_name}\n"
                stats_text += f"- Messages: {chat_message_count}\n"
                stats_text += f"- Latest [{date_str}]: {message_text}\n\n"
        
        if len(chats) > 5:
            stats_text += f"... and {len(chats) - 5} more chats"
        
        await message.reply(stats_text)
        
    except Exception as e:
        logger.exception(f"Error in stats command: {e}")
        await message.reply(f"Error fetching statistics: {str(e)}")


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