"""
Minimal Queue Manager Demo with Chat Binder
"""

import random

from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message

from botspot.commands_menu import botspot_command
from botspot.components.new.chat_binder import get_binding_records
from botspot.components.new.queue_manager import QueueItem, create_queue, get_queue
from botspot.utils import send_safe
from examples.base_bot import App, main, router


class QueueManagerDemoApp(App):
    name = "Queue Manager Demo"


@botspot_command("start", "Start the bot")
@router.message(Command("start"))
async def start_handler(message: Message):
    await message.reply(
        "Queue Manager Demo:\n"
        "- /bind_chat to bind this chat\n"
        "- Send messages to add to queue\n"
        "- /get_random_item to get random item"
    )


@botspot_command("get_random_item", "Get random item")
@router.message(Command("get_random_item"))
async def get_random_item_handler(message: Message):
    user_id = message.from_user.id
    try:
        queue = get_queue()
    except KeyError:
        queue = create_queue()
    items = await queue.get_items(user_id=user_id)
    if not items:
        await send_safe(message.chat.id, "Queue is empty.")
        return
    random_item = random.choice(items)
    await send_safe(message.chat.id, random_item.data)


@router.message(F.text)
async def message_handler(message: Message):
    if not message.from_user or not message.text or message.text.startswith("/"):
        return
    user_id = message.from_user.id

    # Only process messages in bound chats
    bindings = await get_binding_records(user_id, message.chat.id)
    if not bindings:
        return

    # Add message to queue
    try:
        queue = get_queue()
    except KeyError:
        queue = create_queue()

    item = QueueItem(data=message.text)
    await queue.add_item(item, user_id=user_id)
    await message.reply("Added to queue!")


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    main(routers=[router], AppClass=QueueManagerDemoApp)
