"""Queue Manager component for Botspot.

Provides functionality to manage queues of items stored in MongoDB.

Features:
- Create and manage queues with different properties
- Add, get, and remove items from queues
- Support for priority queues
- Mark items as done
"""

import random
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from aiogram.filters import Command
from aiogram.types import Message
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger

logger = get_logger()


class QueueManagerSettings(BaseSettings):
    enabled: bool = False
    collection_prefix: str = "queue_"
    commands_visible: bool = False

    class Config:
        env_prefix = "BOTSPOT_QUEUE_MANAGER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class QueueItem(BaseModel):
    """Base model for queue items."""

    value: str
    added_at: datetime = Field(default_factory=datetime.now)
    priority: int = 0
    is_done: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


T = TypeVar("T", bound=QueueItem)


class Queue(Generic[T]):
    """Queue class that provides an interface to a MongoDB collection."""

    def __init__(self, collection_name: str, item_model: Type[T]):
        self.collection_name = collection_name
        self.item_model = item_model

    async def add_item(self, item: T) -> str:
        """Add an item to the queue."""
        collection = await self._get_collection()
        result = await collection.insert_one(item.model_dump())
        return str(result.inserted_id)

    async def add_value(
        self, value: str, priority: int = 0, metadata: Dict[str, Any] = None
    ) -> str:
        """Add a simple value to the queue."""
        item = self.item_model(value=value, priority=priority, metadata=metadata or {})
        return await self.add_item(item)

    async def get_next_item(self, mark_done: bool = True) -> Optional[T]:
        """Get the next item from the queue based on priority and insertion order."""
        collection = await self._get_collection()
        query = {"is_done": False}

        # Sort by priority (higher first) and then by added_at (older first)
        item_dict = await collection.find_one(query, sort=[("priority", -1), ("added_at", 1)])

        if not item_dict:
            return None

        if mark_done:
            await collection.update_one({"_id": item_dict["_id"]}, {"$set": {"is_done": True}})
            item_dict["is_done"] = True

        # Convert ObjectId to string for serialization
        if "_id" in item_dict:
            item_dict["_id"] = str(item_dict["_id"])

        return self.item_model(**item_dict)

    async def get_random_item(self, mark_done: bool = True) -> Optional[T]:
        """Get a random item from the queue."""
        collection = await self._get_collection()
        query = {"is_done": False}

        # Count total items available
        count = await collection.count_documents(query)
        if count == 0:
            return None

        # Get a random item
        random_index = random.randint(0, count - 1)
        item_dict = await collection.find(query).skip(random_index).limit(1).to_list(length=1)

        if not item_dict:
            return None

        item_dict = item_dict[0]

        if mark_done:
            await collection.update_one({"_id": item_dict["_id"]}, {"$set": {"is_done": True}})
            item_dict["is_done"] = True

        # Convert ObjectId to string for serialization
        if "_id" in item_dict:
            item_dict["_id"] = str(item_dict["_id"])

        return self.item_model(**item_dict)

    async def get_all_items(self, include_done: bool = False) -> List[T]:
        """Get all items from the queue."""
        collection = await self._get_collection()
        query = {} if include_done else {"is_done": False}

        items = await collection.find(query).to_list(length=1000)

        # Convert ObjectId to string for serialization
        for item in items:
            if "_id" in item:
                item["_id"] = str(item["_id"])

        return [self.item_model(**item) for item in items]

    async def mark_item_done(self, item_id: str, done: bool = True) -> bool:
        """Mark an item as done or not done."""
        from bson import ObjectId

        collection = await self._get_collection()

        result = await collection.update_one(
            {"_id": ObjectId(item_id)}, {"$set": {"is_done": done}}
        )

        return result.modified_count > 0

    async def clear_queue(self, include_done: bool = True) -> int:
        """Clear all items from the queue."""
        collection = await self._get_collection()
        query = {} if include_done else {"is_done": False}

        result = await collection.delete_many(query)
        return result.deleted_count

    async def _get_collection(self):
        """Get the MongoDB collection for this queue."""
        from botspot.utils.deps_getters import get_database

        db = get_database()
        return db[self.collection_name]


class QueueManager:
    """Manager for multiple queues."""

    def __init__(self, settings: QueueManagerSettings):
        self.settings = settings
        self.collection_prefix = settings.collection_prefix
        self._queues = {}

    def get_queue(self, key: str = "default", item_model: Type[T] = QueueItem) -> Queue[T]:
        """Get a queue by key."""
        collection_name = f"{self.collection_prefix}{key}"

        if collection_name not in self._queues:
            self._queues[collection_name] = Queue(collection_name, item_model)

        return self._queues[collection_name]

    async def copy_queue(self, source_key: str, target_key: str) -> int:
        """Copy all items from one queue to another."""
        source_queue = self.get_queue(source_key)
        target_queue = self.get_queue(target_key)

        items = await source_queue.get_all_items(include_done=True)
        count = 0

        for item in items:
            await target_queue.add_item(item)
            count += 1

        return count


# Command handlers
async def add_to_queue_handler(message: Message):
    """Add a message to the default queue."""
    if message.text is None:
        return

    user_id = message.from_user.id if message.from_user else 0
    queue_manager = get_queue_manager()
    queue = queue_manager.get_queue(str(user_id))

    await queue.add_value(message.text)
    await message.reply("Added to queue!")


async def next_queue_item_handler(message: Message):
    """Get the next item from the queue."""
    if not message.reply_to_message or not message.reply_to_message.text:
        return

    if "next" not in message.text.lower():
        return

    user_id = message.from_user.id if message.from_user else 0
    queue_manager = get_queue_manager()
    queue = queue_manager.get_queue(str(user_id))

    item = await queue.get_next_item()
    if item:
        await message.reply(f"Next item: {item.value}")
    else:
        await message.reply("Queue is empty!")


async def random_queue_item_handler(message: Message):
    """Get a random item from the queue."""
    if not message.reply_to_message or not message.reply_to_message.text:
        return

    if "random" not in message.text.lower():
        return

    user_id = message.from_user.id if message.from_user else 0
    queue_manager = get_queue_manager()
    queue = queue_manager.get_queue(str(user_id))

    item = await queue.get_random_item()
    if item:
        await message.reply(f"Random item: {item.value}")
    else:
        await message.reply("Queue is empty!")


async def show_queue_handler(message: Message):
    """Show all items in the queue."""
    user_id = message.from_user.id if message.from_user else 0
    queue_manager = get_queue_manager()
    queue = queue_manager.get_queue(str(user_id))

    items = await queue.get_all_items()
    if items:
        item_list = "\n".join([f"- {item.value}" for item in items])
        await message.reply(f"Queue items:\n{item_list}")
    else:
        await message.reply("Queue is empty!")


async def clear_queue_handler(message: Message):
    """Clear all items from the queue."""
    user_id = message.from_user.id if message.from_user else 0
    queue_manager = get_queue_manager()
    queue = queue_manager.get_queue(str(user_id))

    count = await queue.clear_queue()
    await message.reply(f"Queue cleared! Removed {count} items.")


def setup_dispatcher(dp):
    """Setup dispatcher with queue management commands."""
    # Main commands
    dp.message.register(add_to_queue_handler)
    dp.message.register(next_queue_item_handler)
    dp.message.register(random_queue_item_handler)

    # Command-based handlers
    dp.message.register(show_queue_handler, Command("queue_show"))
    dp.message.register(clear_queue_handler, Command("queue_clear"))

    return dp


def initialize(settings: QueueManagerSettings) -> QueueManager:
    """Initialize the queue manager component."""
    from botspot.core.dependency_manager import get_dependency_manager

    # Check that MongoDB is available
    deps = get_dependency_manager()
    if not deps.botspot_settings.mongo_database.enabled:
        raise RuntimeError("MongoDB is required for queue_manager component")

    # Register commands with bot_commands_menu if available
    if settings.commands_visible:
        try:
            from botspot.components.qol.bot_commands_menu import Visibility, add_command

            add_command("queue_show", "Show all items in your queue", Visibility.PUBLIC)(
                show_queue_handler
            )
            add_command("queue_clear", "Clear all items from your queue", Visibility.PUBLIC)(
                clear_queue_handler
            )
        except ImportError:
            logger.warning(
                "bot_commands_menu component not available, skipping command registration"
            )

    logger.info("Queue Manager initialized")
    return QueueManager(settings)


def get_queue_manager() -> QueueManager:
    """Get the queue manager instance."""
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    return deps.queue_manager
