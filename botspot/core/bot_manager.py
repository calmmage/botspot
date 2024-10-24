"""
BotManager class is responsible for setting up the bot, dispatcher etc.
"""

from typing import Optional

from aiogram import Bot, Dispatcher

from botspot.components import (
    error_handler,
    trial_mode,
    event_scheduler,
    print_bot_url,
    bot_commands_menu,
    mongo_database,
    ask_user_handler,
)
from botspot.core.dependency_manager import DependencyManager
from botspot.core.nbl_settings import NBLSettings
from botspot.utils.common import Singleton


class BotManager(metaclass=Singleton):
    def __init__(self, bot: Optional[Bot] = None, **kwargs):
        self.settings = NBLSettings(**kwargs)
        self.deps = DependencyManager(nbl_settings=self.settings, bot=bot)

        if self.settings.mongo_database.enabled:
            self.deps.mongo_database = mongo_database.initialise(self.settings.mongo_database)

        if self.settings.event_scheduler.enabled:
            self.deps.scheduler = event_scheduler.initialise(self.settings.event_scheduler)

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
                raise RuntimeError("Bot instance is required for ask_user functionality")

            ask_user_handler.setup_dispatcher(dp)

    # def setup_bot(self, bot):
