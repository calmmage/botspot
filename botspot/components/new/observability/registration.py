"""Private owner menu registration; no global Telegram menu is changed."""

from urllib.parse import urlsplit

from aiogram.types import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
    BotCommandScopeDefault,
    MenuButtonWebApp,
    WebAppInfo,
)
from loguru import logger


def dashboard_url(public_url: str, page: str = "dashboard") -> str:
    """Build a dashboard link from an HTTPS deployment origin."""
    parsed = urlsplit(public_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Observability public URL must use HTTPS without credentials")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError(
            "Observability public URL must be an origin without path, query or fragment"
        )
    return public_url.rstrip("/") + "/botspot/" + page


async def register_owner_menu(bot, admins: list[str], public_url: str) -> None:
    """Register owner-private buttons and append commands, preserving existing ones.

    Telegram cannot resolve a private user by username. Username-only admins are
    registered when a verified update or login supplies their numeric Telegram ID.
    """
    url = dashboard_url(public_url)
    for admin in dict.fromkeys(str(admin).strip() for admin in admins):
        if not admin.isdigit() or int(admin) <= 0:
            logger.info("Dashboard menu awaits a verified numeric ID for username admin")
            continue
        scope = BotCommandScopeChat(chat_id=int(admin))
        existing = await bot.get_my_commands(scope=scope)
        if not existing:
            existing = await bot.get_my_commands(scope=BotCommandScopeAllPrivateChats())
        if not existing:
            existing = await bot.get_my_commands(scope=BotCommandScopeDefault())
        commands = {command.command: command for command in existing}
        commands.update(
            dashboard=BotCommand(command="dashboard", description="Open dashboard"),
            logs=BotCommand(command="logs", description="Open logs"),
        )
        await bot.set_chat_menu_button(
            chat_id=int(admin),
            menu_button=MenuButtonWebApp(text="Dashboard", web_app=WebAppInfo(url=url)),
        )
        await bot.set_my_commands(commands=list(commands.values()), scope=scope)
