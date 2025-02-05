from datetime import datetime

from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from pydantic_settings import BaseSettings

from botspot.components.bot_commands_menu import add_command
from botspot.utils.internal import get_logger

logger = get_logger()


class BotInfoSettings(BaseSettings):
    enabled: bool = True
    hide_command: bool = False  # hide command from bot command menu
    show_detailed_settings: bool = True

    # todo: admin_only (only show to admins)
    #  admin usernames / ids

    class Config:
        env_prefix = "BOTSPOT_BOT_INFO_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Store bot start time
_start_time = datetime.now()


async def bot_info_handler(message: Message):
    """Show bot information and settings"""
    import botspot
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    settings = deps.botspot_settings

    if not settings.bot_info.enabled:
        return

    # Calculate uptime
    uptime = datetime.now() - _start_time

    # Build response
    response = [
        f"🤖 Bot Information",
        f"Botspot Version: {botspot.__version__}",
        # todo: add main app version from something like __main__.version if available
        f"Uptime: {uptime.days}d {uptime.seconds // 3600}h {(uptime.seconds // 60) % 60}m",
        "\n📊 Enabled Components:",
    ]

    # Add enabled components
    for field in settings.__fields__:
        component_settings = getattr(settings, field)
        if hasattr(component_settings, "enabled"):
            status = "✅" if component_settings.enabled else "❌"
            response.append(f"{status} {field}")

    if settings.bot_info.show_detailed_settings:
        # model dump
        response.append(f"\n📊 Detailed Settings:")
        response.append(settings.model_dump_json(indent=2))

    await message.answer("\n".join(response))


def setup_dispatcher(dp: Dispatcher):
    """Register message handlers"""
    from botspot.core.dependency_manager import get_dependency_manager

    settings = get_dependency_manager().botspot_settings

    if settings.bot_info.enabled:
        dp.message.register(bot_info_handler, Command("bot_info"))
        if not settings.bot_info.hide_command:
            # todo: check that bot command menu is enabled
            add_command("bot_info", "Show bot information and status", visibility="hidden")(
                bot_info_handler
            )
