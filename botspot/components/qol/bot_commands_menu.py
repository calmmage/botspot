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


class GroupDisplayMode(Enum):
    NESTED = "nested"  # Group commands under visibility (visibility -> group -> commands)
    FLAT = "flat"  # Show visibility and groups at the same level (group -> commands)


class CommandInfo(NamedTuple):
    """Command metadata"""

    description: str
    visibility: Visibility = Visibility.PUBLIC
    group: str = None  # None means use the default visibility-based grouping


class BotCommandsMenuSettings(BaseSettings):
    enabled: bool = True
    admin_id: int = 0
    botspot_help: bool = True
    group_display_mode: str = GroupDisplayMode.NESTED.value
    default_group: str = "General"
    sort_commands: bool = True  # Sort commands alphabetically by default

    class Config:
        env_prefix = "BOTSPOT_BOT_COMMANDS_MENU_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def display_mode(self) -> GroupDisplayMode:
        """Get the group display mode as an enum"""
        return GroupDisplayMode(self.group_display_mode)


commands: Dict[str, CommandInfo] = {}
NO_COMMAND_DESCRIPTION = "No description"


def get_commands_by_visibility(
    include_admin: bool = False, settings: BotCommandsMenuSettings = None
) -> str:
    """
    Get formatted list of commands grouped by visibility and/or command group based on settings

    Args:
        include_admin: Whether to include admin commands in the output
        settings: BotCommandsMenuSettings instance with display preferences

    Returns:
        Formatted string with command list
    """
    # Use default settings if none provided
    if settings is None:
        settings = BotCommandsMenuSettings()

    result = []

    # Handle based on display mode
    if settings.display_mode == GroupDisplayMode.NESTED:
        # NESTED MODE: First by visibility, then by group
        return _format_nested_commands(include_admin, settings)
    else:
        # FLAT MODE: Group takes precedence, then visibility at the end
        return _format_flat_commands(include_admin, settings)


def _format_nested_commands(include_admin: bool, settings: BotCommandsMenuSettings) -> str:
    """Format commands in nested mode: visibility -> group -> commands"""
    # First level: visibility, second level: group, third level: commands
    grouped_commands: Dict[Visibility, Dict[str, List[Tuple[str, str]]]] = defaultdict(
        lambda: defaultdict(list)
    )

    # Group commands by visibility and command group
    for cmd, info in commands.items():
        # Skip admin commands if not requested
        if info.visibility == Visibility.ADMIN_ONLY and not include_admin:
            continue

        # Use default group if none specified
        group = info.group if info.group is not None else settings.default_group
        grouped_commands[info.visibility][group].append((cmd, info.description))

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
            result.append(f"\n{group_name.title()}:")
            for cmd, desc in sorted(cmds):
                result.append(f"  /{cmd} - {desc}")

    return "\n".join(result) if result else "No commands available"


def _format_flat_commands(include_admin: bool, settings: BotCommandsMenuSettings) -> str:
    """Format commands in flat mode: explicit groups first, then visibility-based groups"""
    # Group commands by explicit group or visibility
    groups: Dict[str, List[Tuple[str, str, Visibility]]] = defaultdict(list)

    # Visibility-based fallback groups
    visibility_groups = {
        Visibility.PUBLIC: "📝 Public commands",
        Visibility.HIDDEN: "🕵️ Hidden commands",
        Visibility.ADMIN_ONLY: "👑 Admin commands",
    }

    # Process each command
    for cmd, info in commands.items():
        # Skip admin commands if not requested
        if info.visibility == Visibility.ADMIN_ONLY and not include_admin:
            continue

        if info.group is not None:
            # If explicit group is specified, use it
            groups[info.group].append((cmd, info.description, info.visibility))
        else:
            # Otherwise use visibility-based group
            group_name = visibility_groups[info.visibility]
            groups[group_name].append((cmd, info.description, info.visibility))

    # Format output
    result = []

    # First output explicitly grouped commands (sorted alphabetically)
    explicit_groups = [g for g in groups.keys() if g not in visibility_groups.values()]
    for group_name in sorted(explicit_groups):
        result.append(f"{group_name.title()}:")
        for cmd, desc, _ in sorted(groups[group_name]):
            result.append(f"  /{cmd} - {desc}")
        result.append("")  # Empty line between groups

    # Then output visibility-based groups in specific order
    for visibility, group_name in visibility_groups.items():
        if group_name in groups and visibility != Visibility.ADMIN_ONLY:
            result.append(f"{group_name.title()}:")
            for cmd, desc, _ in sorted(groups[group_name]):
                result.append(f"  /{cmd} - {desc}")
            result.append("")  # Empty line between groups

    # Admin commands last if included
    admin_group = visibility_groups[Visibility.ADMIN_ONLY]
    if include_admin and admin_group in groups:
        result.append(f"{admin_group}:")
        for cmd, desc, _ in sorted(groups[admin_group]):
            result.append(f"  /{cmd} - {desc}")

    return "\n".join(result).strip() if result else "No commands available"


async def set_aiogram_bot_commands(bot: Bot, settings: BotCommandsMenuSettings = None):
    """
    Set bot commands for display in Telegram interface

    Args:
        bot: Bot instance
        settings: Settings instance (creates default if None)
    """
    # Use default settings if none provided
    if settings is None:
        settings = BotCommandsMenuSettings()

    all_commands = {}

    # Get all public commands
    for cmd, info in commands.items():
        if info.visibility == Visibility.PUBLIC:  # Only add visible commands to menu
            if cmd in all_commands:
                logger.warning(
                    f"User-defined command /{cmd} overrides default command. "
                    f"Default: '{all_commands[cmd].description}' -> User: '{info.description}'"
                )
            all_commands[cmd] = info

    # Create bot commands list
    bot_commands = []

    # Generate commands list using different approaches based on settings
    if settings.sort_commands:
        # Sort commands alphabetically
        for c, info in sorted(all_commands.items()):
            logger.info(f"Setting bot command: /{c} - {info.description}")
            bot_commands.append(BotCommand(command=c, description=info.description))
    else:
        # Use original order (order of registration)
        for c, info in all_commands.items():
            logger.info(f"Setting bot command: /{c} - {info.description}")
            bot_commands.append(BotCommand(command=c, description=info.description))

    # Set commands in Telegram
    await bot.set_my_commands(bot_commands)


def setup_dispatcher(dp: Dispatcher, settings: BotCommandsMenuSettings):
    # Register startup handler with settings
    async def set_commands_with_settings(bot: Bot):
        await set_aiogram_bot_commands(bot, settings)

    dp.startup.register(set_commands_with_settings)

    if settings.botspot_help:
        from aiogram.types import Message

        @add_command("help_botspot", "Show available bot commands")
        @dp.message(Command("help_botspot"))
        async def help_botspot_cmd(message: Message):
            """Show available bot commands"""
            from botspot.utils.user_ops import is_admin

            assert message.from_user is not None
            help_text = get_commands_by_visibility(
                include_admin=is_admin(message.from_user), settings=settings
            )
            await message.answer(help_text)


def add_botspot_command(
    func=None, names=None, description=None, visibility=Visibility.PUBLIC, group=None
):
    """
    Add a command to the bot's command list

    Args:
        func: The function to decorate (optional)
        names: Command name(s) to register
        description: Command description
        visibility: Command visibility (PUBLIC, HIDDEN, ADMIN_ONLY)
        group: Command group for organizing in help text. If None, will use the default
               group based on display mode settings
    """
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


def botspot_command(names=None, description=None, visibility=Visibility.PUBLIC, group=None):
    """
    Add a command to the bot's command list

    Args:
        names: Command name(s) to register
        description: Command description
        visibility: Command visibility (PUBLIC, HIDDEN, ADMIN_ONLY)
        group: Command group for organizing in help text. If None, will use the default
               group based on display mode settings
    """
    visibility = Visibility(visibility)

    def wrapper(func):
        add_botspot_command(func, names, description, visibility, group)
        return func

    return wrapper


add_command = deprecated("Please use commands_menu.botspot_command instead")(botspot_command)


def add_hidden_command(names=None, description=None, group=None):
    """
    Add a hidden command to the bot's command list

    Args:
        names: Command name(s) to register
        description: Command description
        group: Command group for organizing in help text
    """
    return add_command(names, description, visibility=Visibility.HIDDEN, group=group)


def add_admin_command(names=None, description=None, group=None):
    """
    Add an admin-only command to the bot's command list

    Args:
        names: Command name(s) to register
        description: Command description
        group: Command group for organizing in help text
    """
    return add_command(names, description, visibility=Visibility.ADMIN_ONLY, group=group)


if __name__ == "__main__":
    from unittest.mock import AsyncMock, MagicMock

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

    # Add commands with default grouping
    @botspot_command("about", "About the bot")
    @router.message(Command("about"))
    async def cmd_about(message: Message):
        await message.answer("This is a sample bot")

    @add_admin_command("admin", "Admin only command")
    @router.message(Command("admin"))
    async def cmd_admin(message: Message):
        await message.answer("Admin only")

    # Print all registered commands with NESTED mode (default) and sorting enabled
    nested_settings = BotCommandsMenuSettings(
        group_display_mode=GroupDisplayMode.NESTED.value, sort_commands=True
    )
    print("\n\n=== NESTED DISPLAY MODE (SORTED) ===")
    print(get_commands_by_visibility(include_admin=True, settings=nested_settings))

    # Create a fake bot to demonstrate sorted commands
    mock_bot = MagicMock()
    mock_bot.set_my_commands = AsyncMock()
    print("\n\n=== COMMAND LIST (SORTED) ===")
    import asyncio

    asyncio.run(set_aiogram_bot_commands(mock_bot, nested_settings))

    # Print all registered commands with FLAT mode and sorting disabled
    flat_settings = BotCommandsMenuSettings(
        group_display_mode=GroupDisplayMode.FLAT.value, sort_commands=False
    )
    print("\n\n=== FLAT DISPLAY MODE (UNSORTED) ===")
    print(get_commands_by_visibility(include_admin=True, settings=flat_settings))

    # Demonstrate unsorted commands
    print("\n\n=== COMMAND LIST (UNSORTED) ===")
    mock_bot.set_my_commands.reset_mock()
    asyncio.run(set_aiogram_bot_commands(mock_bot, flat_settings))
