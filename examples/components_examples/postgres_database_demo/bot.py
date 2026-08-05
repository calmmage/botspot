"""Minimal PostgreSQL + session usage demo."""

from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import text

from botspot.commands_menu import botspot_command
from botspot.components.data.postgres_database import get_session
from examples.base_bot import App, main, router


class PostgresDemoApp(App):
    name = "Postgres Database Demo"


@botspot_command("start", "Start the bot")
@router.message(Command("start"))
async def start_handler(message: Message):
    await message.reply("Postgres demo: /ping_db")


@botspot_command("ping_db", "Run SELECT 1 via async session")
@router.message(Command("ping_db"))
async def ping_db_handler(message: Message):
    async with get_session() as session:
        result = await session.execute(text("SELECT 1"))
        value = result.scalar_one()
    await message.reply(f"db ok: {value}")


if __name__ == "__main__":
    main(routers=[router], AppClass=PostgresDemoApp)
