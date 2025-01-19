from typing import List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic_settings import BaseSettings

from botspot.utils.deps_getters import get_database


class AppConfig(BaseSettings):
    """Basic app configuration"""

    telegram_bot_token: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


class App:
    name = "Telegram Tech Sketches"

    def __init__(self, **kwargs):
        self.config = AppConfig(**kwargs)
        self._db: Optional[AsyncIOMotorDatabase] = None

    @property
    def db(self) -> AsyncIOMotorDatabase:
        if self._db is None:
            self._db = get_database()
        return self._db

    async def add_item(self, user_id: int, text: str, created_at) -> bool:
        """Add a new item to the database."""
        result = await self.db.items.insert_one(
            {"user_id": user_id, "text": text, "created_at": created_at}
        )
        return bool(result.inserted_id)

    async def get_items(self, user_id: int) -> List[dict]:
        """Get all items for a user."""
        return await self.db.items.find({"user_id": user_id}).to_list(length=None)
