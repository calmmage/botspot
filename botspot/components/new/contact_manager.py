from typing import TYPE_CHECKING

from pydantic_settings import BaseSettings

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorCollection  # noqa: F401


class ContactManagerSettings(BaseSettings):
    enabled: bool = False

    class Config:
        env_prefix = "BOTSPOT_CONTACT_MANAGER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class ContactManager:
    pass


def setup_dispatcher(dp):
    return dp


def initialize(settings: ContactManagerSettings) -> ContactManager:
    pass


def get_contact_manager():
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    return deps.contact_manager
