"""
Settings Menu Demo Bot

This example shows how to use the Settings Menu component to provide a UI for managing
both admin settings (for components like LLM Provider) and user settings.
"""

import asyncio
import logging
import os
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv

from botspot.components.data.user_data import User
from botspot.components.qol.settings_menu import SettingType, SettingCategory, SettingVisibility
from botspot.core.bot_manager import BotManager
from botspot.utils.deps_getters import get_settings_registry


# Configure logging
logging.basicConfig(level=logging.INFO)


# Extended User class with additional settings fields
class CustomUser(User):
    """Custom user class with additional settings"""
    
    # Add settings dict to store user preferences
    settings: dict = {}


async def register_custom_settings():
    """Register some custom settings for the demo"""
    # Get settings registry
    registry = get_settings_registry()
    
    # Add a custom user setting
    registry.register_setting(
        registry.Setting(
            key="theme",
            name="UI Theme",
            description="Select your preferred UI theme",
            type=SettingType.OPTION,
            category=SettingCategory.APPEARANCE,
            visibility=SettingVisibility.USER,
            default_value="light",
            options=["light", "dark", "system"]
        )
    )
    
    # Add a custom admin setting
    registry.register_setting(
        registry.Setting(
            key="message_limit",
            name="Daily Message Limit",
            description="Maximum number of messages a user can send per day",
            type=SettingType.NUMBER,
            category=SettingCategory.ADVANCED,
            visibility=SettingVisibility.ADMIN,
            default_value=100,
            min_value=10,
            max_value=1000
        )
    )


async def startup_actions(dispatcher: Dispatcher):
    """Actions to perform at bot startup"""
    await register_custom_settings()
    logging.info("Settings menu component initialized")


async def check_setting_command(message: Message):
    """Handler to check the value of a user setting"""
    from botspot.components.qol.settings_menu import settings_manager
    
    # Get user ID
    user_id = message.from_user.id
    
    # Get user settings
    notifications = await settings_manager.get_user_setting(user_id, "notifications_enabled")
    language = await settings_manager.get_user_setting(user_id, "user_preferred_language")
    theme = await settings_manager.get_user_setting(user_id, "theme")
    
    # Format response
    response = (
        "📊 Your current settings:\n\n"
        f"🔔 Notifications: {'Enabled' if notifications else 'Disabled'}\n"
        f"🌐 Language: {language}\n"
        f"🎨 Theme: {theme}\n\n"
        "Use /settings to change these values."
    )
    
    await message.answer(response)


async def main():
    """Main function to set up and run the bot"""
    load_dotenv()  # Load .env file
    
    # Configure the bot
    token = os.getenv("BOT_TOKEN")
    if token == "your_bot_token_here":
        print("⚠️ Please set your bot token in the .env file!")
        return
        
    username = os.getenv("BOTSPOT_ADMINS_STR")
    if username == "your_username_here":
        print("⚠️ Please set your Telegram username in BOTSPOT_ADMINS_STR to access admin settings")
    
    # Set user data to memory mode since we disabled MongoDB
    os.environ["BOTSPOT_USER_DATA_STORAGE_TYPE"] = "memory"
    
    bot = Bot(token=token, parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    
    # Initialize BotManager with our custom User class
    manager = BotManager(bot=bot, dispatcher=dp, user_class=CustomUser)
    
    # Register startup action
    dp.startup.register(startup_actions)
    
    # Register check_setting command
    @dp.message(Command("my_settings"))
    async def my_settings_cmd(message: Message):
        await check_setting_command(message)
    
    # Register all component handlers
    manager.setup_dispatcher(dp)
    
    print(f"✅ Bot started! Search for @{bot.username} on Telegram")
    print("Available commands:")
    print("  /settings - Open user settings menu")
    print("  /admin_settings - Open admin settings menu (admin only)")
    print("  /my_settings - Check your current settings")
    
    # Start the bot
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())