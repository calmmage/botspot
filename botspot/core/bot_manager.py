"""
BotManager class is responsible for setting up the bot, dispatcher etc.
"""

from typing import Optional, Type

from aiogram import Bot, Dispatcher
from loguru import logger

from botspot import __version__
from botspot.components.data import mongo_database, user_data
from botspot.components.data.user_data import User
from botspot.components.features import user_interactions
from botspot.components.main import event_scheduler, single_user_mode, telethon_manager, trial_mode
from botspot.components.middlewares import error_handler
from botspot.components.new import chat_binder, chat_fetcher, llm_provider
from botspot.components.qol import bot_commands_menu, bot_info, print_bot_url
from botspot.core.botspot_settings import BotspotSettings
from botspot.core.dependency_manager import DependencyManager
from botspot.utils.internal import Singleton


class BotManager(metaclass=Singleton):
    def __init__(
        self,
        bot: Optional[Bot] = None,
        dispatcher: Optional[Dispatcher] = None,
        user_class: Optional[Type[User]] = None,
        **kwargs,
    ):
        self.settings = BotspotSettings(**kwargs)
        logger.info(f"Using Botspot version {__version__}")
        logger.info(
            f"Initializing BotManager with config: {self.settings.model_dump_json(indent=2)}"
        )
        assert DependencyManager.is_initialized() is False, "BotManager is already initialized"
        self.deps = DependencyManager(
            botspot_settings=self.settings, bot=bot, dispatcher=dispatcher
        )
        self.user_class = user_class

        if self.settings.mongo_database.enabled:
            mongo_client, mongo_db = mongo_database.initialize(self.settings.mongo_database)
            self.deps.mongo_client = mongo_client
            self.deps.mongo_database = mongo_db

        if self.settings.event_scheduler.enabled:
            self.deps.scheduler = event_scheduler.initialize(self.settings.event_scheduler)

        if self.settings.telethon_manager.enabled:
            self.deps.telethon_manager = telethon_manager.initialize(self.settings.telethon_manager)

        if self.settings.user_data.enabled:
            self.deps.user_manager = user_data.initialize(self.settings, user_class=user_class)

        if self.settings.single_user_mode.enabled:
            single_user_mode.initialize(self.settings.single_user_mode)

        if self.settings.chat_binder.enabled:
            self.deps.chat_binder = chat_binder.initialize(self.settings.chat_binder)

        if self.settings.llm_provider.enabled:
            self.deps.llm_provider = llm_provider.initialize(self.settings.llm_provider)

        if self.settings.chat_fetcher.enabled:
            self.deps.chat_fetcher = chat_fetcher.initialize(self.settings.chat_fetcher)

    def setup_dispatcher(self, dp: Dispatcher):
        """Setup dispatcher with components"""
        # Remove global bot check - each component handles its own requirements
        if self.settings.user_data.enabled:
            user_data.setup_dispatcher(dp, **self.settings.user_data.model_dump())

        if self.settings.single_user_mode.enabled:
            single_user_mode.setup_dispatcher(dp)

        if self.settings.error_handling.enabled:
            error_handler.setup_dispatcher(dp)

        if self.settings.mongo_database.enabled:
            mongo_database.setup_dispatcher(dp)

        if self.settings.print_bot_url.enabled:
            print_bot_url.setup_dispatcher(dp)

        if self.settings.bot_commands_menu.enabled:
            bot_commands_menu.setup_dispatcher(dp, self.settings.bot_commands_menu)

        if self.settings.trial_mode.enabled:
            trial_mode.setup_dispatcher(dp)

        if self.settings.ask_user.enabled:
            if not self.deps.bot:
                raise RuntimeError("Bot instance is required for ask_user functionality")

            user_interactions.setup_dispatcher(dp)

        if self.settings.bot_info.enabled:
            bot_info.setup_dispatcher(dp)

        if self.settings.event_scheduler.enabled:
            event_scheduler.setup_dispatcher(dp)

        if self.settings.telethon_manager.enabled:
            telethon_manager.setup_dispatcher(dp)

        if self.settings.chat_binder.enabled:
            chat_binder.setup_dispatcher(dp)

        if self.settings.llm_provider.enabled:
            llm_provider.setup_dispatcher(dp)

        if self.settings.chat_fetcher.enabled:
            chat_fetcher.setup_dispatcher(dp)
