"""
Queue Manager Demo Bot with Chat Binder Integration

This bot demonstrates the combined use of QueueManager and ChatBinder components:
- Use /bind_chat to bind a chat to your user
- Send any message to add it to your queue
- Use /get_random_item to get a random item from your queue
- The bot stores message text in the queue
"""

from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message

from botspot.commands_menu import Visibility, botspot_command
from botspot.components.new.chat_binder import get_chat_binding_status
from botspot.components.new.queue_manager import QueueItem, create_queue, get_queue
from botspot.utils.deps_getters import get_bot
from examples.base_bot import App, main, router


class QueueManagerDemoApp(App):
    name = "Queue Manager with Chat Binder Demo"


@botspot_command("start", "Start the bot")
@router.message(Command("start"))
async def start_handler(message: Message):
    """Send welcome message when user starts the bot."""
    await message.reply(
        "Welcome to Queue Manager with Chat Binder Demo!\n\n"
        "- Use /bind_chat to bind this chat to your user\n"
        "- Send any message to add it to your personal queue\n"
        "- Use /get_random_item to get a random item from your queue\n"
        "- Use /bind_status to check if this chat is bound\n"
    )


@botspot_command("get_random_item", "Get a random item from your queue")
@router.message(Command("get_random_item"))
async def get_random_item_handler(message: Message):
    """Get a random item from the user's queue."""
    if not message.from_user:
        await message.reply("User information is missing.")
        return

    user_id = message.from_user.id

    try:
        # Check if the chat is bound to the user
        bindings = await get_chat_binding_status(user_id, message.chat.id)
        if not bindings:
            await message.reply("This chat is not bound to you. Use /bind_chat first.")
            return

        # Get the user's queue
        try:
            queue = get_queue(f"user_{user_id}")
        except KeyError:
            await message.reply("Your queue is empty. Send some messages to add items.")
            return

        # Get all items
        items = await queue.get_items(str(user_id))
        if not items:
            await message.reply("Your queue is empty. Send some messages to add items.")
            return

        # Get a random item
        import random

        random_item = random.choice(items)

        await message.reply(f"Random item from your queue: {random_item.get('data', 'No data')}")
    except Exception as e:
        await message.reply(f"Error getting random item: {str(e)}")


# Handler to add messages to the queue
@router.message(F.text)
async def message_handler(message: Message):
    """Add any text message to the user's queue."""
    if not message.from_user or not message.text or message.text.startswith("/"):
        return

    user_id = message.from_user.id

    try:
        # Check if the chat is bound to the user
        bindings = await get_chat_binding_status(user_id, message.chat.id)
        if not bindings:
            # Chat is not bound, ignore the message
            return

        # Get or create the user's queue
        try:
            queue = get_queue(f"user_{user_id}")
        except KeyError:
            queue = create_queue(f"user_{user_id}", QueueItem)

        # Add the message to the queue
        item = QueueItem(data=message.text)
        await queue.add_item(item, username=str(user_id))

        await message.reply("Message added to your queue!")
    except Exception as e:
        print(f"Error adding message to queue: {str(e)}")


async def check_admin_status(chat_id):
    """Check if the bot is an admin in the chat."""
    bot = get_bot()
    try:
        chat_member = await bot.get_chat_member(chat_id=chat_id, user_id=bot.id)
        return chat_member.status in ["administrator", "creator"]
    except Exception:
        return False


@botspot_command("check_admin", "Check if bot is admin in this chat")
@router.message(Command("check_admin"))
async def check_admin_handler(message: Message):
    """Check if the bot is an admin in this chat."""
    is_admin = await check_admin_status(message.chat.id)
    if is_admin:
        await message.reply("I am an admin in this chat! ✅")
    else:
        await message.reply("I am NOT an admin in this chat. ❌")


async def get_chat_members(chat_id, limit=10):
    """Get members from a chat (requires admin rights or chat_fetcher)."""
    bot = get_bot()
    try:
        # This is a simplified implementation - in a real bot,
        # you would use chat_fetcher component if available
        chat_admins = await bot.get_chat_administrators(chat_id)
        return [
            {
                "user_id": member.user.id,
                "username": member.user.username,
                "full_name": member.user.full_name,
                "status": member.status,
            }
            for member in chat_admins[:limit]
        ]
    except Exception as e:
        print(f"Error getting chat members: {str(e)}")
        return []


@botspot_command("list_members", "List chat members (admin only)")
@router.message(Command("list_members"))
async def list_members_handler(message: Message):
    """List members in the chat (requires bot to be admin)."""
    if not await check_admin_status(message.chat.id):
        await message.reply("I need to be an admin to list members.")
        return

    members = await get_chat_members(message.chat.id)
    if not members:
        await message.reply("Could not retrieve chat members.")
        return

    member_list = "\n".join(
        [
            f"- {member['full_name']} (@{member['username'] or 'No username'}) - {member['status']}"
            for member in members
        ]
    )

    await message.reply(f"Chat members (up to 10 admins):\n{member_list}")


if __name__ == "__main__":
    # Override environment variables
    import os

    os.environ["BOTSPOT_MONGO_DATABASE_ENABLED"] = "true"
    os.environ["BOTSPOT_MONGO_DATABASE_DATABASE"] = "queue_manager_demo"
    os.environ["BOTSPOT_QUEUE_MANAGER_ENABLED"] = "true"
    os.environ["BOTSPOT_CHAT_BINDER_ENABLED"] = "true"
    os.environ["BOTSPOT_CHAT_BINDER_COMMANDS_VISIBLE"] = "true"
    os.environ["BOTSPOT_BOT_COMMANDS_MENU_ENABLED"] = "true"

    main(routers=[router], AppClass=QueueManagerDemoApp)
