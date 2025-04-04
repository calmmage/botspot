from aiogram.filters import Command
from aiogram.types import Message

from botspot.commands_menu import botspot_command
from botspot.user_interactions import ask_user, ask_user_choice
from examples.base_bot import App, main, router


class AskUserDemoApp(App):
    name = "Ask User Demo"


@botspot_command("demo", "Demo command showcasing ask_user functionality")
@router.message(Command("demo"))
async def demo_command(message: Message, state) -> None:
    """Simple demo of asking user for their name"""
    response = await ask_user(message.chat.id, "What's your name?", state, timeout=30.0)
    if response:
        await message.reply(f"Hello, {response}! Nice to meet you!")
    else:
        await message.reply("Demo cancelled due to timeout.")


@botspot_command("choose", "Demo command showcasing button choices")
@router.message(Command("choose"))
async def choose_command(message: Message, state) -> None:
    """Demo of asking user to choose from options"""
    choices = ["Red", "Green", "Blue"]
    response = await ask_user_choice(
        message.chat.id, "What's your favorite color?", choices, state, timeout=30.0
    )
    if response:
        await message.reply(f"You chose: {response}!")
    else:
        await message.reply("No color was chosen.")


if __name__ == "__main__":
    main(routers=[router], AppClass=AskUserDemoApp)
