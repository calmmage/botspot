from typing import TYPE_CHECKING, Optional

from aiogram import Bot, Dispatcher

from botspot.core.botspot_settings import BotspotSettings
from botspot.utils.internal import Singleton

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from motor.motor_asyncio import (  # noqa: F401
        AsyncIOMotorClient,
        AsyncIOMotorCollection,
        AsyncIOMotorDatabase,
    )

    from botspot.components.data.user_data import UserManager
    from botspot.components.main.telethon_manager import TelethonManager
    from botspot.components.new.llm_provider import LLMProvider
    from botspot.components.new.queue_manager import QueueManager


class DependencyManager(metaclass=Singleton):
    def __init__(
        self,
        botspot_settings: Optional[BotspotSettings] = None,
        bot: Optional[Bot] = None,
        dispatcher: Optional[Dispatcher] = None,
        mongo_client: Optional["AsyncIOMotorClient"] = None,
        mongo_database: Optional["AsyncIOMotorDatabase"] = None,
        **kwargs
    ):
        self._botspot_settings = botspot_settings or BotspotSettings()
        self._bot = bot
        self._dispatcher = dispatcher
        self._mongo_client = mongo_client
        self._mongo_database = mongo_database
        self._scheduler = None
        self._telethon_manager = None
        self._user_manager = None
        self._chat_binder = None
        self._llm_provider = None
        self._queue_manager = None
        self.__dict__.update(kwargs)

    @property
    def botspot_settings(self) -> BotspotSettings:
        return self._botspot_settings

    # @botspot_settings.setter
    # def botspot_settings(self, value):
    #     self._botspot_settings = value

    @property
    def bot(self) -> Bot:
        if self._bot is None:
            raise RuntimeError("Bot is not initialized")
        return self._bot

    @bot.setter
    def bot(self, value):
        self._bot = value

    @property
    def dispatcher(self) -> Dispatcher:
        if self._dispatcher is None:
            raise RuntimeError("Dispatcher is not initialized")
        return self._dispatcher

    @dispatcher.setter
    def dispatcher(self, value):
        self._dispatcher = value

    @property
    def mongo_client(self) -> "AsyncIOMotorClient":
        if self._mongo_client is None:
            raise RuntimeError("MongoDB client is not initialized")
        return self._mongo_client

    @mongo_client.setter
    def mongo_client(self, value):
        self._mongo_client = value

    @property
    def mongo_database(self) -> "AsyncIOMotorDatabase":
        if self._mongo_database is None:
            raise RuntimeError("MongoDB database is not initialized")
        return self._mongo_database

    @mongo_database.setter
    def mongo_database(self, value):
        self._mongo_database = value

    @property
    def scheduler(self) -> "AsyncIOScheduler":
        if self._scheduler is None:
            raise RuntimeError("Scheduler is not initialized")
        return self._scheduler

    @scheduler.setter
    def scheduler(self, value):
        self._scheduler = value

    @property
    def telethon_manager(self) -> "TelethonManager":
        if self._telethon_manager is None:
            raise RuntimeError("Telethon manager is not initialized")
        return self._telethon_manager

    @telethon_manager.setter
    def telethon_manager(self, value):
        self._telethon_manager = value

    @property
    def user_manager(self) -> "UserManager":
        if self._user_manager is None:
            raise RuntimeError("User manager is not initialized")
        return self._user_manager

    @user_manager.setter
    def user_manager(self, value):
        self._user_manager = value

    @property
    def chat_binder(self) -> "AsyncIOMotorCollection":
        if self._chat_binder is None:
            raise RuntimeError("Bind chat is not initialized")
        return self._chat_binder

    @chat_binder.setter
    def chat_binder(self, value):
        self._chat_binder = value

    @property
    def llm_provider(self) -> "LLMProvider":
        if self._llm_provider is None:
            raise RuntimeError("LLM Provider is not initialized")
        return self._llm_provider

    @llm_provider.setter
    def llm_provider(self, value):
        self._llm_provider = value
        
    @property
    def queue_manager(self) -> "QueueManager":
        if self._queue_manager is None:
            raise RuntimeError("Queue Manager is not initialized")
        return self._queue_manager
        
    @queue_manager.setter
    def queue_manager(self, value):
        self._queue_manager = value

    @classmethod
    def is_initialized(cls) -> bool:
        return cls in cls._instances


def get_dependency_manager() -> DependencyManager:
    if not DependencyManager.is_initialized():
        raise ValueError("Dependency manager is not initialized")
    return DependencyManager()
