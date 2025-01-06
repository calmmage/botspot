from enum import Enum
from typing import Dict, NamedTuple

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger

logger = get_logger()


class Visibility(Enum):
    PUBLIC = "public"
    HIDDEN = "hidden"
    ADMIN_ONLY = "admin_only"


class CommandInfo(NamedTuple):
    """Command metadata"""

    description: str
    visibility: Visibility = Visibility.PUBLIC


class BotCommandsMenuSettings(BaseSettings):
    enabled: bool = True
    default_commands: dict[str, str] = {"start": "Start the bot"}
    admin_id: int = 0

    class Config:
        env_prefix = "BOTSPOT_BOT_COMMANDS_MENU_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


commands: Dict[str, CommandInfo] = {}
NO_COMMAND_DESCRIPTION = "No description"


async def set_aiogram_bot_commands(bot: Bot):
    settings = BotCommandsMenuSettings()
    all_commands = {}

    # First add default commands
    for cmd, desc in settings.default_commands.items():
        all_commands[cmd] = CommandInfo(desc, visibility=Visibility.PUBLIC)

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


def setup_dispatcher(dp: Dispatcher):
    dp.startup.register(set_aiogram_bot_commands)


def add_command(names=None, description=None, visibility=Visibility.PUBLIC):
    """Add a command to the bot's command list"""

    def wrapper(func):
        nonlocal names
        nonlocal description
        nonlocal visibility

        if names is None:
            names = [func.__name__]
        elif isinstance(names, str):
            names = [names]
        if not description:
            description = func.__doc__.strip() or NO_COMMAND_DESCRIPTION

        for n in names:
            n = n.lower()
            n = n.lstrip("/")  # just in case
            if n in commands:
                logger.warning(f"Trying to add duplicate command: /{n} - skipping")
                continue
            commands[n] = CommandInfo(description, visibility=visibility)
        return func

    return wrapper


def add_hidden_command(names=None, description=None):
    """Add a hidden command to the bot's command list"""
    return add_command(names, description, visibility=Visibility.HIDDEN)


def add_admin_command(names=None, description=None):
    """Add an admin-only command to the bot's command list"""
    return add_command(names, description, visibility=Visibility.ADMIN_ONLY)
