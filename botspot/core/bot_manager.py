"""
BotManager class is responsible for setting up the bot, dispatcher etc.
"""

from typing import Optional

from aiogram import Bot, Dispatcher

from botspot.components import (
    ask_user_handler,
    bot_commands_menu,
    bot_info,
    error_handler,
    event_scheduler,
    mongo_database,
    print_bot_url,
    telethon_manager,
    trial_mode,
)
from botspot.core.botspot_settings import BotspotSettings
from botspot.core.dependency_manager import DependencyManager
from botspot.utils.internal import Singleton


class BotManager(metaclass=Singleton):
    def __init__(
        self,
        bot: Optional[Bot] = None,
        dispatcher: Optional[Dispatcher] = None,
        **kwargs
    ):
        self.settings = BotspotSettings(**kwargs)
        self.deps = DependencyManager(
            botspot_settings=self.settings, bot=bot, dispatcher=dispatcher
        )

        if self.settings.mongo_database.enabled:
            self.deps.mongo_database = mongo_database.initialise(
                self.settings.mongo_database
            )

        if self.settings.event_scheduler.enabled:
            self.deps.scheduler = event_scheduler.initialise(
                self.settings.event_scheduler
            )

        if self.settings.telethon_manager.enabled:
            self.deps.telethon_manager = telethon_manager.initialise(
                self.settings.telethon_manager
            )

    def setup_dispatcher(self, dp: Dispatcher):
        """Setup dispatcher with components"""
        # Remove global bot check - each component handles its own requirements

        if self.settings.error_handling.enabled:
            error_handler.setup_dispatcher(dp)

        if self.settings.mongo_database.enabled:
            mongo_database.setup_dispatcher(dp)

        if self.settings.print_bot_url.enabled:
            print_bot_url.setup_dispatcher(dp)

        if self.settings.bot_commands_menu.enabled:
            bot_commands_menu.setup_dispatcher(dp)

        if self.settings.trial_mode.enabled:
            trial_mode.setup_dispatcher(dp)

        if self.settings.ask_user.enabled:
            if not self.deps.bot:
                raise RuntimeError(
                    "Bot instance is required for ask_user functionality"
                )

            ask_user_handler.setup_dispatcher(dp)

        if self.settings.bot_info.enabled:
            bot_info.setup_dispatcher(dp)

        if self.settings.event_scheduler.enabled:
            event_scheduler.setup_dispatcher(dp)

        if self.settings.telethon_manager.enabled:
            telethon_manager.setup_dispatcher(dp)
