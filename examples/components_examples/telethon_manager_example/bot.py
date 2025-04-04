"""
Example usage of the telethon_manager component.
"""

from aiogram import html
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from botspot.commands_menu import botspot_command
from botspot.components.main.telethon_manager import get_telethon_manager
from botspot.components.main.trial_mode import add_global_limit, add_user_limit
from examples.base_bot import App, main, router


@botspot_command("example", "Test the bot - telethon_manager example")
@router.message(Command("example"))
async def example_handler(message: Message, state: FSMContext):
    telethon_manager = get_telethon_manager()
    assert message.from_user is not None
    client = await telethon_manager.get_client(message.from_user.id, state=state)

    assert client is not None, "Client is None"

    few_random_dialogs = await client.get_dialogs()

    await message.answer(f"Loaded {len(few_random_dialogs)} dialogs.")


class TelethonManagerExampleApp(App):
    name = "Telethon Manager Example"
    # async def on_startup(self):
    #     # Add global limit
    #     add_global_limit("example_global_limit", 5)
    #
    #     # Add user limit
    #     add_user_limit("example_user_limit", 2)
    #
    #     await super().on_startup()


if __name__ == "__main__":
    main(router, AppClass=TelethonManagerExampleApp)
