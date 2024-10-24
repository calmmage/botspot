from typing import TYPE_CHECKING, Optional

from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger

if TYPE_CHECKING:
    from pymongo import Database, Collection

logger = get_logger()


class MongoDatabaseSettings(BaseSettings):
    enabled: bool = False
    conn_str: str = "mongodb://localhost:27017"
    database: str = "test"

    class Config:
        env_prefix = "NBL_MONGO_DATABASE_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class DatabaseManager:
    def __init__(self, db: "Database"):
        self._db = db

    def get_collection(self, name: str) -> "Collection":
        """Get collection by name"""
        return self._db[name]


def initialise(settings: MongoDatabaseSettings) -> "Database":
    """Initialize MongoDB connection"""
    from pymongo import MongoClient

    logger.info("Initializing MongoDB connection")
    try:
        client = MongoClient(settings.conn_str)
        db = client[settings.database]

        # Test connection
        db.list_collection_names()

        logger.info("MongoDB connection successful")
        return db
    except Exception as e:
        logger.error(f"Failed to initialize MongoDB: {e}")
        raise


def setup_dispatcher(dp):
    """No dispatcher setup needed for database component"""
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    if not deps.mongo_database:
        logger.warning("MongoDB is not initialized")
        return dp

    # Create database manager instance
    deps.db_manager = DatabaseManager(deps.mongo_database)
    logger.info("Database manager initialized")

    return dp


def get_db_manager() -> Optional[DatabaseManager]:
    """Helper function to get database manager from dependency manager"""
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    return getattr(deps, "db_manager", None)
