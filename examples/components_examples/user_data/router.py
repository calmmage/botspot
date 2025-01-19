"""Router module for handling telegram bot commands."""

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app import App, UserType
from botspot.components.bot_commands_menu import add_command
from botspot.utils import send_safe

router = Router()
app = App()


@add_command("start", "Start the bot")
@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    """Register new user and send welcome message."""
    user = await app.get_user(message.from_user.id)
    await send_safe(
        message.chat.id,
        f"Hello {user.full_name}! Welcome to {app.name}!\n"
        f"Your timezone is set to: {user.timezone}\n"
        f"User type: {user.user_type.value}",
    )


@add_command("help", "Show this help message")
@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    """Show help message."""
    # First check if user is admin to show admin commands
    is_admin = await app.is_admin(message.from_user.id)

    base_commands = (
        f"Commands:\n"
        f"/start - Register and get welcome message\n"
        f"/me - Show your profile info\n"
        f"/stats - Show user statistics\n"
        f"/help - Show this help message"
    )

    admin_commands = (
        f"\n\nAdmin commands:\n"
        f"/make_admin <user_id> - Promote user to admin\n"
        f"/make_friend <user_id> - Set user as friend\n"
        f"/make_regular <user_id> - Set user as regular"
    )

    await send_safe(
        message.chat.id,
        f"This is {app.name}.\n\n"
        f"{base_commands}"
        f"{admin_commands if is_admin else ''}",
    )


@add_command("me", "Show your profile info")
@router.message(Command("me"))
async def profile_handler(message: Message) -> None:
    """Show user profile information."""
    user = await app.get_user(message.from_user.id)
    if not user:
        await send_safe(
            message.chat.id, "Error: User not found. Please use /start first."
        )
        return

    await send_safe(
        message.chat.id,
        f"Your profile:\n"
        f"ID: {user.user_id}\n"
        f"Name: {user.full_name}\n"
        f"Username: @{user.username or 'not set'}\n"
        f"User type: {user.user_type.value}\n"
        f"Timezone: {user.timezone}\n"
        f"Registered: {user.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        f"Last active: {user.last_active.strftime('%Y-%m-%d %H:%M:%S UTC')}",
    )


@add_command("stats", "Show user statistics")
@router.message(Command("stats"))
async def stats_handler(message: Message) -> None:
    """Show user statistics."""
    stats = await app.get_user_stats()

    await send_safe(
        message.chat.id,
        f"User Statistics:\n"
        f"Total users: {stats['total']}\n\n"
        f"By type:\n"
        f"- Admins: {stats['by_type'][UserType.ADMIN]}\n"
        f"- Friends: {stats['by_type'][UserType.FRIEND]}\n"
        f"- Regular: {stats['by_type'][UserType.REGULAR]}",
    )


@add_command("make_admin", "Promote user to admin")
@router.message(Command("make_admin"))
async def make_admin_handler(message: Message) -> None:
    """Promote user to admin. Only available to admins."""
    if not await app.is_admin(message.from_user.id):
        await send_safe(message.chat.id, "Error: Only admins can use this command.")
        return

    try:
        user_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        await send_safe(message.chat.id, "Error: Please provide valid user ID.")
        return

    if await app.set_user_type(user_id, UserType.ADMIN):
        await send_safe(message.chat.id, f"User {user_id} promoted to admin.")
    else:
        await send_safe(message.chat.id, f"Error: Could not promote user {user_id}.")


@add_command("make_friend", "Set user as friend")
@router.message(Command("make_friend"))
async def make_friend_handler(message: Message) -> None:
    """Set user as friend. Only available to admins."""
    if not await app.is_admin(message.from_user.id):
        await send_safe(message.chat.id, "Error: Only admins can use this command.")
        return

    try:
        user_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        await send_safe(message.chat.id, "Error: Please provide valid user ID.")
        return

    if await app.set_user_type(user_id, UserType.FRIEND):
        await send_safe(message.chat.id, f"User {user_id} set as friend.")
    else:
        await send_safe(message.chat.id, f"Error: Could not update user {user_id}.")


@add_command("make_regular", "Set user as regular")
@router.message(Command("make_regular"))
async def make_regular_handler(message: Message) -> None:
    """Set user as regular. Only available to admins."""
    if not await app.is_admin(message.from_user.id):
        await send_safe(message.chat.id, "Error: Only admins can use this command.")
        return

    try:
        user_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        await send_safe(message.chat.id, "Error: Please provide valid user ID.")
        return

    if await app.set_user_type(user_id, UserType.REGULAR):
        await send_safe(message.chat.id, f"User {user_id} set as regular.")
    else:
        await send_safe(message.chat.id, f"Error: Could not update user {user_id}.")
