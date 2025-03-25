from typing import TYPE_CHECKING, Tuple

from pydantic import SecretStr
from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase  # noqa: F401

logger = get_logger()


class MongoDatabaseSettings(BaseSettings):
    enabled: bool = False
    conn_str: SecretStr = SecretStr("mongodb://localhost:27017")
    database: str = "test"

    class Config:
        env_prefix = "BOTSPOT_MONGO_DATABASE_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


def setup_dispatcher(dp):
    return dp


def get_database() -> "AsyncIOMotorDatabase":
    """Get MongoDB database instance from dependency manager."""
    from botspot.core.dependency_manager import get_dependency_manager

    db = get_dependency_manager().mongo_database
    if db is None:
        raise RuntimeError("MongoDB database is not initialized")
    return db


def get_mongo_client() -> "AsyncIOMotorClient":
    """Get MongoDB client instance from dependency manager."""
    from botspot.core.dependency_manager import get_dependency_manager

    client = get_dependency_manager().mongo_client
    if client is None:
        raise RuntimeError(
            "MongoDB client is not initialized. Make sure MongoDB is enabled in settings."
        )
    return client


def initialize(
    settings: MongoDatabaseSettings,
) -> Tuple["AsyncIOMotorClient", "AsyncIOMotorDatabase"]:
    """Initialize MongoDB connection and return both client and database."""
    from motor.motor_asyncio import AsyncIOMotorClient

    assert AsyncIOMotorClient

    client = AsyncIOMotorClient(settings.conn_str.get_secret_value())
    db = client[settings.database]
    logger.info("MongoDB client initialized.")
    return client, db
