"""Router module for handling telegram bot commands."""

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from app import App
from dotenv import load_dotenv

from botspot.commands_menu import botspot_command
from botspot.utils import send_safe

load_dotenv()

router = Router()
app = App()


@botspot_command("start", "Start the bot")
@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    """Handle the /start command."""
    await send_safe(
        message,
        f"Hello! Welcome to {app.name}!\n\n"
        f"Commands:\n"
        f"/add <text> - Add a new item\n"
        f"/list - List all items\n"
        f"/help - Show this help message",
    )


@botspot_command("help", "Show this help message")
@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    """Basic help command handler."""
    await send_safe(
        message,
        f"This is {app.name}.\n\nCommands:\n/add <text> - Add a new item\n/list - List all items",
    )


@botspot_command("add", "Add a new item")
@router.message(Command("add"))
async def add_item_handler(message: Message) -> None:
    """Add a new item to the database."""
    assert message.text is not None
    text = message.text.replace("/add", "").strip()
    if not text:
        await send_safe(message.chat.id, "Please provide some text to add.\nUsage: /add <text>")
        return

    try:
        assert message.from_user is not None
        success = await app.add_item(
            user_id=message.from_user.id, text=text, created_at=message.date
        )
        if success:
            await send_safe(message.chat.id, f"Added new item: {text}")
        else:
            await send_safe(message.chat.id, "Failed to add item. Please try again.")
    except Exception:
        await send_safe(message.chat.id, "Error adding item to database. Please try again later.")
        raise


@botspot_command("list", "List all items")
@router.message(Command("list"))
async def list_items_handler(message: Message) -> None:
    """List all items from the database."""
    try:
        assert message.from_user is not None
        items = await app.get_items(user_id=message.from_user.id)

        if not items:
            await send_safe(message.chat.id, "No items found. Use /add to add some items.")
            return

        response = "Your items:\n\n"
        for i, item in enumerate(items, 1):
            response += f"{i}. {item['text']}\n"

        await send_safe(message.chat.id, response)
    except Exception:
        await send_safe(
            message.chat.id,
            "Error retrieving items from database. Please try again later.",
        )
        raise
