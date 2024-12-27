from aiogram import Dispatcher, Bot
from aiogram.types import BotCommand
from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger

logger = get_logger()


class BotCommandsMenuSettings(BaseSettings):
    enabled: bool = True
    default_commands: dict[str, str] = {
        "start": "Start the bot"
    }

    class Config:
        env_prefix = "BOTSPOT_BOT_COMMANDS_MENU_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


commands = {}
NO_COMMAND_DESCRIPTION = "No description"


async def set_aiogram_bot_commands(bot: Bot):
    settings = BotCommandsMenuSettings()
    all_commands = {}

    # First add default commands
    all_commands.update(settings.default_commands)

    # Then add user commands, logging any overrides
    for cmd, desc in commands.items():
        if cmd in all_commands:
            logger.warning(
                f"User-defined command /{cmd} overrides default command. "
                f"Default: '{all_commands[cmd]}' -> User: '{desc}'"
            )
        all_commands[cmd] = desc
    
    bot_commands = []
    for c, d in all_commands.items():
        logger.info(f"Setting bot command: /{c} - {d}")
        bot_commands.append(BotCommand(command=c, description=d))
    await bot.set_my_commands(bot_commands)


def setup_dispatcher(dp: Dispatcher):
    dp.startup.register(set_aiogram_bot_commands)


# decorator to add commands
def add_command(names=None, description=None):
    def wrapper(func):
        nonlocal names
        nonlocal description

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
            commands[n] = description
        return func

    return wrapper
