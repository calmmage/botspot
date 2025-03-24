from aiogram.filters import Command
from aiogram.types import Message

from botspot.commands_menu import botspot_command
from botspot.components.new.chat_binder import get_bind_chat_id, get_user_bound_chats
from examples.base_bot import App, main, router


class ChatBinderDemoApp(App):
    name = "Chat Binder Demo"


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
        # todo: send url instead.
        await message.reply(f"Bound chat for key '{key}': {chat_id}, url: https://t.me/c/{chat_id}")
    except Exception as e:
        await message.reply(f"Error: {str(e)}")


if __name__ == "__main__":
    main(routers=[router], AppClass=ChatBinderDemoApp)
