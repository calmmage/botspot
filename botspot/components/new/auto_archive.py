from typing import TYPE_CHECKING

from pydantic_settings import BaseSettings

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorCollection  # noqa: F401


class AutoArchiveSettings(BaseSettings):
    enabled: bool = False

    class Config:
        env_prefix = "BOTSPOT_AUTO_ARCHIVE_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class AutoArchive:
    pass


def setup_dispatcher(dp):
    return dp


def initialize(settings: AutoArchiveSettings) -> AutoArchive:
    pass


def get_name() -> AutoArchive:
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    return deps.name
