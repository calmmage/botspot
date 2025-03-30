import random

from aiogram.filters import Command
from aiogram.types import Message

from botspot import send_safe
from botspot.commands_menu import botspot_command
from botspot.components.new.chat_fetcher import get_chat_fetcher
from examples.base_bot import App, main, router


class ChatFetcherDemoApp(App):
    name = "Chat Fetcher Demo"


# 3 more handlers:
# get_chats
# find_chat
# find_message
@botspot_command("use_get_chats", "Get all chats")
@router.message(Command("use_get_chats"))
async def use_get_chats_handler(message: Message):
    chat_fetcher = get_chat_fetcher()
    assert message.from_user is not None
    result = await chat_fetcher.get_chats(message.from_user.id)

    # Calculate stats
    total_users = len(result.users)
    total_groups = len(result.groups)
    total_channels = len(result.channels)

    # Count owned chats (where user is creator/admin)
    owned_groups = sum(1 for chat in result.groups if getattr(chat, "creator", False))
    owned_channels = sum(1 for chat in result.channels if getattr(chat, "creator", False))

    stats = f"""📊 Chat Statistics:
Total Users: {total_users}
Total Groups: {total_groups} (You own: {owned_groups})
Total Channels: {total_channels} (You own: {owned_channels})
Total Chats: {total_users + total_groups + total_channels}
"""
    chat_list = "\n\nDetailed List:\n"
    chat_list += "\nChats with people:\n"
    users = list(result.users)
    random.shuffle(users)
    for chat in users[:10]:
        chat_list += f"{chat.id}: {chat.username}\n"

    chat_list += "\nYour groups:\n"
    groups = list(result.groups)
    random.shuffle(groups)
    for chat in groups[:10]:
        chat_list += f"{chat.id}: {chat.title}\n"

    chat_list += "\nYour channels:\n"
    channels = list(result.channels)
    random.shuffle(channels)
    for chat in channels[:10]:
        chat_list += f"{chat.id}: {chat.title}\n"

    await send_safe(message.chat.id, stats + chat_list)


@botspot_command("use_find_chat", "Find a chat by name")
@router.message(Command("use_find_chat"))
async def find_chat_handler(message: Message):
    chat_fetcher = get_chat_fetcher()
    query = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
    chats = await chat_fetcher.search_chat(query)

    if not chats:
        await message.reply(f"No chats found matching '{query}'")
        return

    chat_list = "\n".join([f"{chat.id}: {chat.name}" for chat in chats])
    await message.reply(f"Found chats:\n{chat_list}")


@botspot_command("find_message", "Find a message by text")
@router.message(Command("find_message"))
async def find_message_handler(message: Message):
    chat_fetcher = get_chat_fetcher()
    query = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
    messages = await chat_fetcher.search_message(query)

    if not messages:
        await message.reply(f"No messages found matching '{query}'")
        return

    message_list = "\n".join([f"{msg.id}: {msg.text}" for msg in messages])
    await message.reply(f"Found messages:\n{message_list}")


@botspot_command("get_messages", "Get messages from a chat")
@router.message(Command("get_messages"))
async def get_messages_handler(message: Message):
    chat_fetcher = get_chat_fetcher()
    chat_id = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""

    if not chat_id:
        # need to help user find the chat interactively
        from botspot.user_interactions import ask_user, ask_user_choice

        search_query = await ask_user(message.from_user.id, "Please enter chat name to search for:")
        chats = await chat_fetcher.search_chat(search_query)
        if not chats:
            await message.reply(f"No chats found matching '{search_query}'")
            return
        choices = {str(chat.id): chat.title for chat in chats}
        selected = await ask_user_choice(message.from_user.id, "Select a chat:", choices)
        if selected is None:
            await message.reply("Operation cancelled")
            return
        assert isinstance(selected, str)

        chat_id = chats[selected].id
    messages = await chat_fetcher.get_chat_messages(chat_id, user_id=message.from_user.id)

    if not messages:
        await message.reply(f"No messages found in chat '{chat_id}'")
        return

    message_list = "\n".join([f"{msg.id}: {msg.text}" for msg in messages])
    await message.reply(f"Messages from chat '{chat_id}':\n{message_list}")


if __name__ == "__main__":
    main(routers=[router], AppClass=ChatFetcherDemoApp)
