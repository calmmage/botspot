"""Product metrics demo: enable Mongo and configure owner/public URL in environment."""

from aiogram.filters import Command
from aiogram.types import Message

from botspot.commands_menu import botspot_command
from botspot.observability import record_usage
from examples.base_bot import App, main, router


class ObservabilityDemo(App):
    name = "Observability demo"


@botspot_command("ping", "Record a product event")
@router.message(Command("ping"))
async def ping(message: Message):
    await record_usage("ping", outcome="ok", cost=0, model="demo")
    await message.answer("Pong. View this request in your dashboard.")


if __name__ == "__main__":
    main(routers=[router], AppClass=ObservabilityDemo)
