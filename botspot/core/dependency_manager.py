from typing import TYPE_CHECKING

from aiogram import Bot

from botspot.core.botspot_settings import BotspotSettings
from botspot.utils.internal import Singleton

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from pymongo import Database


class DependencyManager(metaclass=Singleton):
    def __init__(self, botspot_settings: BotspotSettings = None, bot: Bot = None, mongo_database=None, **kwargs):
        self._botspot_settings = botspot_settings or BotspotSettings()
        self._bot = bot
        self._mongo_database = mongo_database
        self._scheduler = None
        self.__dict__.update(kwargs)

    @property
    def botspot_settings(self) -> BotspotSettings:
        return self._botspot_settings

    # @botspot_settings.setter
    # def botspot_settings(self, value):
    #     self._botspot_settings = value

    @property
    def bot(self) -> Bot:
        return self._bot

    @bot.setter
    def bot(self, value):
        self._bot = value

    @property
    def mongo_database(self) -> "Database":
        return self._mongo_database

    @mongo_database.setter
    def mongo_database(self, value):
        self._mongo_database = value

    @property
    def scheduler(self) -> "AsyncIOScheduler":
        return self._scheduler

    @scheduler.setter
    def scheduler(self, value):
        self._scheduler = value

    @classmethod
    def is_initialized(cls) -> bool:
        return cls in cls._instances


def get_dependency_manager() -> DependencyManager:
    if not DependencyManager.is_initialized():
        raise ValueError("Dependency manager is not initialized")
    return DependencyManager()
