import random
from typing import Optional

from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
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
    if message.from_user is None:
        await message.reply("Error: User not found")
        return

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
async def find_chat_handler(message: Message, state: FSMContext):
    if message.from_user is None:
        await send_safe(message.chat.id, "Error: User not found")
        return

    chat_fetcher = get_chat_fetcher()
    query = ""
    if message.text:
        parts = message.text.split(maxsplit=1)
        query = parts[1] if len(parts) > 1 else ""

    while query is None or not query:
        from botspot.user_interactions import ask_user

        query = await ask_user(
            message.from_user.id, "Please enter chat name to search for:", state=state
        )

    chats = await chat_fetcher.search_chat(query, user_id=message.from_user.id)

    if not chats:
        await send_safe(message.chat.id, f"No chats found matching '{query}'")
        return

    chat_list = "\n".join(
        [f"{chat.id}: {getattr(chat, 'name', getattr(chat, 'title', 'Unknown'))}" for chat in chats]
    )
    await send_safe(message.chat.id, f"Found chats:\n{chat_list}")


# @botspot_command("find_message", "Find a message by text")
# @router.message(Command("find_message"))
# async def find_message_handler(message: Message, state: FSMContext):
#     if message.from_user is None:
#         await message.reply("Error: User not found")
#         return
#
#     chat_fetcher = get_chat_fetcher()
#     query = ""
#     if message.text:
#         parts = message.text.split(maxsplit=1)
#         query = parts[1] if len(parts) > 1 else ""
#
#     while query is None or not query:
#         from botspot.user_interactions import ask_user
#         query = await ask_user(message.from_user.id, "Please enter message text to search for:", state=state)
#
#     messages = await chat_fetcher.search_message(query, user_id=message.from_user.id)
#
#     if not messages:
#         await message.reply(f"No messages found matching '{query}'")
#         return
#
#     message_list = "\n".join(
#         [
#             f"{getattr(msg, 'id', 'Unknown ID')}: {getattr(msg, 'text', 'No text')}"
#             for msg in messages
#         ]
#     )
#     await message.reply(f"Found messages:\n{message_list}")


@botspot_command("get_messages", "Get messages from a chat")
@router.message(Command("get_messages"))
async def get_messages_handler(message: Message, state: FSMContext):
    if message.from_user is None:
        await send_safe(message.chat.id, "Error: User not found")
        return

    chat_fetcher = get_chat_fetcher()
    chat_id: Optional[int] = None
    chat_id_str = ""

    if message.text:
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            try:
                chat_id = int(parts[1])
            except ValueError:
                chat_id_str = parts[1]

    if chat_id is None:
        # need to help user find the chat interactively
        from botspot.user_interactions import ask_user, ask_user_choice

        search_query = await ask_user(
            message.from_user.id,
            "Please enter chat name to search for:",
            state=state,
        )

        # Handle potential None from ask_user
        if not search_query:
            search_query = ""

        chats = await chat_fetcher.search_chat(search_query, user_id=message.from_user.id)
        if not chats:
            await send_safe(message.chat.id, f"No chats found matching '{search_query}'")
            return

        choices = {
            str(i): f"{getattr(chat, 'title', getattr(chat, 'name', 'Unknown'))} ({chat.id})"
            for i, chat in enumerate(chats)
        }
        selected = await ask_user_choice(
            message.from_user.id,
            "Select a chat:",
            choices,
            state=state,
        )
        if selected is None:
            await send_safe(message.chat.id, "Operation cancelled")
            return

        chat_id = chats[int(selected)].id

    messages = await chat_fetcher.get_chat_messages(chat_id, user_id=message.from_user.id)

    if not messages:
        await send_safe(message.chat.id, f"No messages found in chat '{chat_id}'")
        return

    # Limit display to just 10 messages to avoid overwhelming response
    display_limit = 10
    limited_messages = messages[:display_limit]

    message_list = "\n".join(
        [
            f"{getattr(msg, 'id', 'Unknown ID')}: {getattr(msg, 'text', 'No text')}"
            for msg in limited_messages
        ]
    )

    total_count = len(messages)
    display_info = f"Showing {min(display_limit, total_count)} of {total_count} messages"

    await send_safe(
        message.chat.id, f"Messages from chat '{chat_id}':\n{display_info}\n\n{message_list}"
    )


if __name__ == "__main__":
    main(routers=[router], AppClass=ChatFetcherDemoApp)
