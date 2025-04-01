from typing import TYPE_CHECKING, Optional

from aiogram import Bot, Dispatcher

from botspot.core.botspot_settings import BotspotSettings
from botspot.core.errors import BotspotError
from botspot.utils.internal import Singleton

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase  # noqa: F401

    from botspot.components.data.user_data import UserManager
    from botspot.components.main.telethon_manager import TelethonManager
    from botspot.components.new.auto_archive import AutoArchive
    from botspot.components.new.chat_binder import ChatBinder
    from botspot.components.new.chat_fetcher import ChatFetcher
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
        self._chat_fetcher = None
        self._auto_archive = None
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
            raise BotspotError("Bot is not initialized")
        return self._bot

    @bot.setter
    def bot(self, value):
        self._bot = value

    @property
    def dispatcher(self) -> Dispatcher:
        if self._dispatcher is None:
            raise BotspotError("Dispatcher is not initialized")
        return self._dispatcher

    @dispatcher.setter
    def dispatcher(self, value):
        self._dispatcher = value

    @property
    def mongo_client(self) -> "AsyncIOMotorClient":
        if self._mongo_client is None:
            raise BotspotError("MongoDB client is not initialized")
        return self._mongo_client

    @mongo_client.setter
    def mongo_client(self, value):
        self._mongo_client = value

    @property
    def mongo_database(self) -> "AsyncIOMotorDatabase":
        if self._mongo_database is None:
            raise BotspotError("MongoDB database is not initialized")
        return self._mongo_database

    @mongo_database.setter
    def mongo_database(self, value):
        self._mongo_database = value

    @property
    def scheduler(self) -> "AsyncIOScheduler":
        if self._scheduler is None:
            raise BotspotError("Scheduler is not initialized")
        return self._scheduler

    @scheduler.setter
    def scheduler(self, value):
        self._scheduler = value

    @property
    def telethon_manager(self) -> "TelethonManager":
        if self._telethon_manager is None:
            raise BotspotError("Telethon manager is not initialized")
        return self._telethon_manager

    @telethon_manager.setter
    def telethon_manager(self, value):
        self._telethon_manager = value

    @property
    def user_manager(self) -> "UserManager":
        if self._user_manager is None:
            raise BotspotError("User manager is not initialized")
        return self._user_manager

    @user_manager.setter
    def user_manager(self, value):
        self._user_manager = value

    @property
    def chat_binder(self) -> "ChatBinder":
        if self._chat_binder is None:
            raise BotspotError("Bind chat is not initialized")
        return self._chat_binder

    @chat_binder.setter
    def chat_binder(self, value):
        self._chat_binder = value

    @property
    def llm_provider(self) -> "LLMProvider":
        if self._llm_provider is None:
            raise BotspotError("LLM Provider is not initialized")
        return self._llm_provider

    @llm_provider.setter
    def llm_provider(self, value):
        self._llm_provider = value

    @property
    def queue_manager(self) -> "QueueManager":
        if self._queue_manager is None:
            raise BotspotError("Queue Manager is not initialized")
        return self._queue_manager

    @queue_manager.setter
    def queue_manager(self, value):
        self._queue_manager = value

    @property
    def chat_fetcher(self) -> "ChatFetcher":
        if self._chat_fetcher is None:
            raise BotspotError("Chat Fetcher is not initialized")
        return self._chat_fetcher

    @chat_fetcher.setter
    def chat_fetcher(self, value):
        self._chat_fetcher = value

    @property
    def auto_archive(self) -> "AutoArchive":
        if self._auto_archive is None:
            raise BotspotError("Auto Archive is not initialized")
        return self._auto_archive

    @auto_archive.setter
    def auto_archive(self, value):
        self._auto_archive = value

    @classmethod
    def is_initialized(cls) -> bool:
        return cls in cls._instances


def get_dependency_manager() -> DependencyManager:
    if not DependencyManager.is_initialized():
        raise ValueError("Dependency manager is not initialized")
    return DependencyManager()
