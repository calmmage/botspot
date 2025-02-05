from typing import TYPE_CHECKING

from pydantic import SecretStr
from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorDatabase  # noqa: F401

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


def initialize(settings: MongoDatabaseSettings) -> "AsyncIOMotorDatabase":
    """Initialize MongoDB connection."""
    if not settings.enabled:
        logger.info("MongoDB is disabled.")
        return None

    from motor.motor_asyncio import AsyncIOMotorClient

    assert AsyncIOMotorClient

    try:
        client = AsyncIOMotorClient(settings.conn_str.get_secret_value())
        db = client[settings.database]
        logger.info("MongoDB client initialized.")
        return db
    except Exception as e:
        logger.error(f"Failed to initialize MongoDB: {e}")
        raise
