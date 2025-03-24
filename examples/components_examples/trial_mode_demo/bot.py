from aiogram import html
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from botspot.commands_menu import botspot_command
from botspot.components.main.trial_mode import add_global_limit, add_user_limit
from examples.base_bot import App, main, router


class TrialModeDemoApp(App):
    name = "Trial Mode Demo"


@botspot_command("start", "Start the bot")
@router.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """Send a welcome message when the command /start is issued"""
    assert message.from_user is not None
    await message.answer(
        f"Hello, {html.bold(message.from_user.full_name)}! Welcome to the Trial Mode Demo Bot."
    )


@botspot_command("limited_user", "Command with per-user limit")
@router.message(Command("limited_user"))
@add_user_limit(limit=3, period=60)  # Limit to 3 uses per minute per user
async def limited_user_command(message: Message) -> None:
    """A command with a per-user usage limit"""
    await message.answer(
        "You've used the limited_user command. It has a per-user limit of 3 uses per minute."
    )


@botspot_command("limited_global", "Command with global limit")
@router.message(Command("limited_global"))
@add_global_limit(limit=5, period=60)  # Limit to 5 uses per minute globally
async def limited_global_command(message: Message) -> None:
    """A command with a global usage limit"""
    await message.answer(
        "You've used the limited_global command. It has a global limit of 5 uses per minute."
    )


@botspot_command("unlimited", "Command without usage limits")
@router.message(Command("unlimited"))
async def unlimited_command(message: Message) -> None:
    """A command without any usage limits"""
    await message.answer("This command has no usage limits.")


@router.message()
async def echo_handler(message: Message) -> None:
    """Echo any other message"""
    await message.answer("This is an echo message. It's subject to the global middleware limits.")


if __name__ == "__main__":
    main(routers=[router], AppClass=TrialModeDemoApp)
