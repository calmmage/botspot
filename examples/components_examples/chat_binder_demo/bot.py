from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message

from botspot.commands_menu import botspot_command
from botspot.components.new.chat_binder import get_bind_chat_id, get_user_bound_chats
from botspot.utils.send_safe import send_safe
from examples.base_bot import App, main, router


class ChatBinderDemoApp(App):
    name = "Chat Binder Demo"


@botspot_command("start", "Start the bot")
@router.message(Command("start"))
async def start_handler(message: Message):
    await message.reply(
        "👋 Welcome to Chat Binder Demo!\n\n"
        "This bot demonstrates how to use the chat_binder component to bind chats to users.\n\n"
        "📋 Available commands:\n"
        "/bind_chat [key] - Bind this chat to you with optional key\n"
        "/unbind_chat [key] - Unbind a chat with the given key\n"
        "/list_chats - List all your bound chats\n"
        "/get_chat [key] - Get chat ID for specific key\n\n"
        "🔄 Feature Demo:\n"
        "Any messages you send will be echoed to all your bound chats!"
    )


@botspot_command("list_chats", "List all bound chats")
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

        chats_info = "\n".join(
            [f"Key: {chat.key}, Chat ID: {chat.chat_id}" for chat in bound_chats]
        )
        await message.reply(f"Your bound chats:\n{chats_info}")
    except Exception as e:
        await message.reply(f"Error listing chats: {str(e)}")


@botspot_command("get_chat", "Get bound chat ID for a key")
@router.message(Command("get_chat"))
async def get_chat_handler(message: Message):
    if not message.from_user:
        await message.reply("User information is missing.")
        return

    assert message.text is not None

    key = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else "default"

    try:
        chat_id = await get_bind_chat_id(message.from_user.id, key)
        await message.reply(f"Bound chat for key '{key}': {chat_id}")
    except Exception as e:
        await message.reply(f"Error: {str(e)}")


# Echo feature - demonstrates a practical use of chat binding
@router.message(F.text)
async def echo_to_bound_chats(message: Message):
    """Echo messages to all bound chats."""
    if not message.from_user or not message.text:
        return

    # Get all bound chats for this user
    try:
        bound_chats = await get_user_bound_chats(message.from_user.id)
        if not bound_chats:
            return

        # Count how many chats we'll echo to (excluding the current one)
        echo_count = 0
        for chat in bound_chats:
            if chat.chat_id != message.chat.id:
                # Echo the message to bound chat
                await send_safe(
                    chat.chat_id,
                    f"🔄 Echo from {message.from_user.full_name} (key: {chat.key}):\n{message.text}",
                )
                echo_count += 1

        # Notify user if messages were echoed
        if echo_count > 0:
            await message.reply(f"✅ Your message was echoed to {echo_count} bound chat(s).")
    except Exception as e:
        await message.reply(f"Error echoing to bound chats: {str(e)}")


if __name__ == "__main__":
    main(routers=[router], AppClass=ChatBinderDemoApp)
