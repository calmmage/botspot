from collections import defaultdict
from enum import Enum
from typing import Dict, List, NamedTuple, Tuple

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import BotCommand
from deprecated import deprecated
from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger

logger = get_logger()


class Visibility(Enum):
    PUBLIC = "public"
    HIDDEN = "hidden"  # in /botspot_help command only
    ADMIN_ONLY = "admin_only"


class CommandInfo(NamedTuple):
    """Command metadata"""

    description: str
    visibility: Visibility = Visibility.PUBLIC
    group: str = "General"


class BotCommandsMenuSettings(BaseSettings):
    enabled: bool = True
    admin_id: int = 0
    botspot_help: bool = True

    class Config:
        env_prefix = "BOTSPOT_BOT_COMMANDS_MENU_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


commands: Dict[str, CommandInfo] = {}
NO_COMMAND_DESCRIPTION = "No description"


def get_commands_by_visibility(include_admin: bool = False) -> str:
    """
    Get formatted list of commands grouped by visibility and command group

    Args:
        include_admin: Whether to include admin commands in the output

    Returns:
        Formatted string with command list
    """
    # First level: visibility, second level: group, third level: commands
    grouped_commands: Dict[Visibility, Dict[str, List[Tuple[str, str]]]] = defaultdict(
        lambda: defaultdict(list)
    )

    # Group commands by visibility and command group
    for cmd, info in commands.items():
        grouped_commands[info.visibility][info.group].append((cmd, info.description))

    # Format output
    result = []

    # Process public commands by group
    if grouped_commands[Visibility.PUBLIC]:
        result.append("📝 Public commands:")
        for group_name, cmds in sorted(grouped_commands[Visibility.PUBLIC].items()):
            result.append(f"\n{group_name.title()}:")
            for cmd, desc in sorted(cmds):
                result.append(f"  /{cmd} - {desc}")

    # Process hidden commands by group
    if grouped_commands[Visibility.HIDDEN]:
        result.append("\n🕵️ Hidden commands:")
        for group_name, cmds in sorted(grouped_commands[Visibility.HIDDEN].items()):
            result.append(f"\n{group_name.title()}:")
            for cmd, desc in sorted(cmds):
                result.append(f"  /{cmd} - {desc}")

    # Process admin commands by group (if allowed)
    if include_admin and grouped_commands[Visibility.ADMIN_ONLY]:
        result.append("\n👑 Admin commands:")
        for group_name, cmds in sorted(grouped_commands[Visibility.ADMIN_ONLY].items()):
            result.append(f"\n{group_name}.title():")
            for cmd, desc in sorted(cmds):
                result.append(f"  /{cmd} - {desc}")

    return "\n".join(result) if result else "No commands available"


async def set_aiogram_bot_commands(bot: Bot):
    all_commands = {}

    # Then add user commands (excluding hidden ones)
    for cmd, info in commands.items():
        if info.visibility == Visibility.PUBLIC:  # Only add visible commands to menu
            if cmd in all_commands:
                logger.warning(
                    f"User-defined command /{cmd} overrides default command. "
                    f"Default: '{all_commands[cmd].description}' -> User: '{info.description}'"
                )
            all_commands[cmd] = info

    bot_commands = []
    for c, info in all_commands.items():
        if info.visibility == Visibility.PUBLIC:
            logger.info(f"Setting bot command: /{c} - {info.description}")
            bot_commands.append(BotCommand(command=c, description=info.description))
    await bot.set_my_commands(bot_commands)


def setup_dispatcher(dp: Dispatcher, settings: BotCommandsMenuSettings):
    dp.startup.register(set_aiogram_bot_commands)

    if settings.botspot_help:
        from aiogram.types import Message

        @add_command("help_botspot", "Show available bot commands")
        @dp.message(Command("help_botspot"))
        async def help_botspot_cmd(message: Message):
            """Show available bot commands"""
            from botspot.utils.user_ops import is_admin

            assert message.from_user is not None
            help_text = get_commands_by_visibility(include_admin=is_admin(message.from_user))
            await message.answer(help_text)


def add_botspot_command(
    func=None, names=None, description=None, visibility=Visibility.PUBLIC, group="General"
):
    """Add a command to the bot's command list"""
    visibility = Visibility(visibility)

    if names is None:
        if func is None:
            raise ValueError("Either names or func must be provided")
        names = [func.__name__]
    elif isinstance(names, str):
        names = [names]
    if not description:
        if func is None:
            raise ValueError("Either description or func must be provided")
        docstring = func.__doc__
        if docstring is not None:
            docstring = docstring.strip()
        description = docstring or NO_COMMAND_DESCRIPTION

    for n in names:
        n = n.lower()
        n = n.lstrip("/")  # just in case
        if n in commands:
            logger.warning(f"Trying to add duplicate command: /{n} - skipping")
            continue
        commands[n] = CommandInfo(description, visibility=visibility, group=group)


def botspot_command(names=None, description=None, visibility=Visibility.PUBLIC, group="General"):
    """Add a command to the bot's command list"""
    visibility = Visibility(visibility)

    def wrapper(func):
        add_botspot_command(func, names, description, visibility, group)
        return func

    return wrapper


add_command = deprecated("Please use commands_menu.botspot_command instead")(botspot_command)


def add_hidden_command(names=None, description=None, group="General"):
    """Add a hidden command to the bot's command list"""
    return add_command(names, description, visibility=Visibility.HIDDEN, group=group)


def add_admin_command(names=None, description=None, group="General"):
    """Add an admin-only command to the bot's command list"""
    return add_command(names, description, visibility=Visibility.ADMIN_ONLY, group=group)


if __name__ == "__main__":
    from aiogram import Router
    from aiogram.types import Message

    # Create a router for commands
    router = Router()

    # Register command handlers with decorators
    @botspot_command("start", "Start the bot", group="Basic")
    @router.message(Command("start"))
    async def cmd_start(message: Message):
        await message.answer("Welcome to the bot!")

    @botspot_command("help", "Show available commands", group="Basic")
    @router.message(Command("help"))
    async def cmd_help(message: Message):
        await message.answer("Help message here")

    # Add a hidden command
    @add_hidden_command("secret", "Secret command", group="Advanced")
    @router.message(Command("secret"))
    async def cmd_secret(message: Message):
        await message.answer("This is a hidden command")

    # Add commands with different groups
    @botspot_command("settings", "Change bot settings", group="Settings")
    @router.message(Command("settings"))
    async def cmd_settings(message: Message):
        await message.answer("Settings menu")

    @botspot_command("profile", "View your profile", group="User")
    @router.message(Command("profile"))
    async def cmd_profile(message: Message):
        await message.answer("Your profile")

    # Print all registered commands
    print("Registered commands:")
    print(get_commands_by_visibility(include_admin=True))
