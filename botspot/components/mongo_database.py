from typing import TYPE_CHECKING

from pydantic_settings import BaseSettings

if TYPE_CHECKING:
    from pymongo import Database


# option 1: pymongo


class MongoDatabaseSettings(BaseSettings):
    enabled: bool = False
    conn_str: str = "mongodb://localhost:27017"
    database: str = "test"

    class Config:
        env_prefix = "BOTSPOT_MONGO_DATABASE_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


def setup_dispatcher(dp):
    # return dp
    pass


def initialise(settings: MongoDatabaseSettings) -> "Database":
    from pymongo import MongoClient

    client = MongoClient(settings.conn_str)
    db = client[settings.database]

    return db
