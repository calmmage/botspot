from aiogram import html
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from botspot.commands_menu import botspot_command
from examples.base_bot import App, main, router


class StandaloneComponentsApp(App):
    name = "Standalone Components Demo"


@botspot_command("start", "Start the bot")
@router.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """Send a welcome message when the command /start is issued"""
    assert message.from_user is not None
    await message.answer(f"Hello, {html.bold(message.from_user.full_name)}!")


@botspot_command("error", "Raise a test exception")
@router.message(Command("error"))
async def command_error_handler(message: Message) -> None:
    """Raise an exception to test error handling"""
    raise Exception("Something Went Wrong")


@router.message()
async def echo_handler(message: Message) -> None:
    try:
        # Send a copy of the received message
        await message.send_copy(chat_id=message.chat.id)
    except TypeError:
        # But not all the types is supported to be copied so need to handle it
        await message.answer("Nice try!")


if __name__ == "__main__":
    main(routers=[router], AppClass=StandaloneComponentsApp)
