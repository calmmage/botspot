from aiogram import Router, html
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from botspot import commands_menu
from botspot.utils import send_safe

from .app import App

router = Router()


@commands_menu.botspot_command("start", "Start the bot")
@router.message(CommandStart())
async def start_handler(message: Message, app: App):
    assert message.from_user is not None
    await send_safe(
        message.chat.id,
        f"Hello, {html.bold(message.from_user.full_name)}!\n"
        f"Welcome to {app.name}!\n"
        f"Use /help to see available commands.",
    )


@commands_menu.botspot_command("help", "Show this help message")
@router.message(Command("help"))
async def help_handler(message: Message, app: App):
    """Basic help command handler"""
    await send_safe(
        message.chat.id,
        f"This is {app.name}. Use /start to begin."
        "Available commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/help_botspot - Show Botspot help\n",
    )
