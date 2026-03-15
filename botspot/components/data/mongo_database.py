from typing import TYPE_CHECKING, Optional, Tuple

from pydantic import SecretStr
from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger

if TYPE_CHECKING:
    from pymongo import AsyncMongoClient  # noqa: F401
    from pymongo.asynchronous.database import AsyncDatabase  # noqa: F401

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


def get_database() -> "AsyncDatabase":
    """Get MongoDB database instance from dependency manager."""
    from botspot.core.dependency_manager import get_dependency_manager

    db = get_dependency_manager().mongo_database
    if db is None:
        raise RuntimeError("MongoDB database is not initialized")
    return db


def get_mongo_client() -> "AsyncMongoClient":
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
) -> Tuple[Optional["AsyncMongoClient"], Optional["AsyncDatabase"]]:
    """Initialize MongoDB connection and return both client and database.

    Args:
        settings: MongoDB settings

    Returns:
        Tuple of (AsyncMongoClient, AsyncDatabase) or (None, None) if disabled

    Raises:
        ImportError: If pymongo is not installed
    """
    # Check if MongoDB is enabled
    if not settings.enabled:
        logger.info("MongoDB is disabled")
        return None, None

    # Check if pymongo is installed
    try:
        from pymongo import AsyncMongoClient
    except ImportError:
        logger.error("pymongo package is not installed. Please install it to use MongoDB.")
        raise ImportError(
            "pymongo package is not installed. Run 'uv add pymongo' or 'pip install pymongo'"
        )

    # Initialize client and database
    client = AsyncMongoClient(settings.conn_str.get_secret_value())
    db = client[settings.database]
    logger.info(f"MongoDB client initialized. Database: {settings.database}")
    return client, db


if __name__ == "__main__":
    import asyncio

    async def simple_db_operation():
        # Get the database instance
        db = get_database()

        # Create a test collection and insert a document
        collection = db["test_collection"]
        await collection.insert_one({"name": "Test User", "created_at": "now"})

        # Find the document
        doc = await collection.find_one({"name": "Test User"})
        print(f"Found document: {doc}")

    asyncio.run(simple_db_operation())
