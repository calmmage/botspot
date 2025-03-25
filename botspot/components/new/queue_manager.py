"""Queue Manager Component for Botspot

This module provides a queue management interface for Botspot, allowing
storage and retrieval of items in MongoDB collections.
"""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Generic, List, Optional, Tuple, TypeVar

from motor.motor_asyncio import AsyncIOMotorCollection
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger

logger = get_logger()

T = TypeVar("T")  # Generic type for queue items


class QueueManagerSettings(BaseSettings):
    """Settings for the Queue Manager component."""

    enabled: bool = False
    collection_prefix: str = "queue_"
    default_key: str = "default"

    class Config:
        env_prefix = "BOTSPOT_QUEUE_MANAGER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@dataclass
class QueueItemMetadata:
    """Metadata for a queue item."""

    item_id: str
    created_at: datetime
    added_by: Optional[int] = None  # User ID who added the item
    updated_at: Optional[datetime] = None
    tags: List[str] = None


class QueueStats(BaseModel):
    """Statistics for a queue."""

    queue_key: str
    total_items: int
    oldest_item_date: Optional[datetime] = None
    newest_item_date: Optional[datetime] = None


class Queue(Generic[T]):
    """A queue for storing and retrieving items."""

    def __init__(self, collection: AsyncIOMotorCollection, key: str = "default"):
        """Initialize a queue with a MongoDB collection and key.

        Args:
            collection: The MongoDB collection to use
            key: The key to identify this queue (default: "default")
        """
        self.collection = collection
        self.key = key

    async def add_item(
        self, item: T, added_by: Optional[int] = None, tags: List[str] = None
    ) -> str:
        """Add an item to the queue.

        Args:
            item: The item to add
            added_by: Optional user ID who added the item
            tags: Optional list of tags for the item

        Returns:
            The ID of the added item
        """
        item_id = str(uuid.uuid4())
        now = datetime.utcnow()

        # Create the document to store
        document = {
            "item_id": item_id,
            "queue_key": self.key,
            "data": item,
            "created_at": now,
            "added_by": added_by,
            "tags": tags or [],
        }

        await self.collection.insert_one(document)
        logger.debug(f"Added item {item_id} to queue {self.key}")
        return item_id

    async def get_item(self, item_id: str) -> Tuple[Optional[T], Optional[QueueItemMetadata]]:
        """Get a specific item by ID.

        Args:
            item_id: The ID of the item to get

        Returns:
            A tuple of (item, metadata) or (None, None) if not found
        """
        document = await self.collection.find_one({"item_id": item_id, "queue_key": self.key})
        if not document:
            return None, None

        metadata = QueueItemMetadata(
            item_id=document["item_id"],
            created_at=document["created_at"],
            added_by=document.get("added_by"),
            updated_at=document.get("updated_at"),
            tags=document.get("tags", []),
        )

        return document["data"], metadata

    async def get_next_item(self) -> Tuple[Optional[T], Optional[QueueItemMetadata]]:
        """Get the next item from the queue (oldest first).

        Returns:
            A tuple of (item, metadata) or (None, None) if queue is empty
        """
        document = await self.collection.find_one(
            {"queue_key": self.key}, sort=[("created_at", 1)]  # Sort by oldest first
        )

        if not document:
            return None, None

        metadata = QueueItemMetadata(
            item_id=document["item_id"],
            created_at=document["created_at"],
            added_by=document.get("added_by"),
            updated_at=document.get("updated_at"),
            tags=document.get("tags", []),
        )

        return document["data"], metadata

    async def get_random_item(self) -> Tuple[Optional[T], Optional[QueueItemMetadata]]:
        """Get a random item from the queue.

        Returns:
            A tuple of (item, metadata) or (None, None) if queue is empty
        """
        # First check if the queue has items
        count = await self.collection.count_documents({"queue_key": self.key})
        if count == 0:
            return None, None

        # Get a random item
        random_item = await self.collection.aggregate(
            [{"$match": {"queue_key": self.key}}, {"$sample": {"size": 1}}]
        ).to_list(1)

        if not random_item:
            return None, None

        document = random_item[0]
        metadata = QueueItemMetadata(
            item_id=document["item_id"],
            created_at=document["created_at"],
            added_by=document.get("added_by"),
            updated_at=document.get("updated_at"),
            tags=document.get("tags", []),
        )

        return document["data"], metadata

    async def remove_item(self, item_id: str) -> bool:
        """Remove an item from the queue.

        Args:
            item_id: The ID of the item to remove

        Returns:
            True if the item was removed, False otherwise
        """
        result = await self.collection.delete_one({"item_id": item_id, "queue_key": self.key})
        return result.deleted_count > 0

    async def update_item(self, item_id: str, item: T) -> bool:
        """Update an item in the queue.

        Args:
            item_id: The ID of the item to update
            item: The new item data

        Returns:
            True if the item was updated, False otherwise
        """
        result = await self.collection.update_one(
            {"item_id": item_id, "queue_key": self.key},
            {"$set": {"data": item, "updated_at": datetime.utcnow()}},
        )
        return result.modified_count > 0

    async def get_all_items(
        self, limit: int = 100, skip: int = 0, sort_by: str = "created_at", ascending: bool = True
    ) -> List[Tuple[T, QueueItemMetadata]]:
        """Get all items in the queue.

        Args:
            limit: Maximum number of items to return
            skip: Number of items to skip
            sort_by: Field to sort by
            ascending: Whether to sort in ascending order

        Returns:
            List of (item, metadata) tuples
        """
        sort_direction = 1 if ascending else -1

        cursor = (
            self.collection.find({"queue_key": self.key})
            .sort(sort_by, sort_direction)
            .skip(skip)
            .limit(limit)
        )

        results = []
        async for document in cursor:
            metadata = QueueItemMetadata(
                item_id=document["item_id"],
                created_at=document["created_at"],
                added_by=document.get("added_by"),
                updated_at=document.get("updated_at"),
                tags=document.get("tags", []),
            )
            results.append((document["data"], metadata))

        return results

    async def get_queue_stats(self) -> QueueStats:
        """Get statistics about the queue.

        Returns:
            QueueStats object containing queue statistics
        """
        total = await self.collection.count_documents({"queue_key": self.key})

        stats = QueueStats(queue_key=self.key, total_items=total)

        if total > 0:
            # Get oldest item
            oldest = await self.collection.find_one(
                {"queue_key": self.key}, sort=[("created_at", 1)]
            )
            stats.oldest_item_date = oldest["created_at"] if oldest else None

            # Get newest item
            newest = await self.collection.find_one(
                {"queue_key": self.key}, sort=[("created_at", -1)]
            )
            stats.newest_item_date = newest["created_at"] if newest else None

        return stats

    async def clear(self) -> int:
        """Clear all items from the queue.

        Returns:
            Number of items removed
        """
        result = await self.collection.delete_many({"queue_key": self.key})
        return result.deleted_count

    async def search_by_tags(
        self, tags: List[str], match_all: bool = False
    ) -> List[Tuple[T, QueueItemMetadata]]:
        """Search for items by tags.

        Args:
            tags: List of tags to search for
            match_all: If True, items must have all tags; if False, items can have any tag

        Returns:
            List of (item, metadata) tuples
        """
        query = {"queue_key": self.key}

        if match_all:
            query["tags"] = {"$all": tags}
        else:
            query["tags"] = {"$in": tags}

        cursor = self.collection.find(query)

        results = []
        async for document in cursor:
            metadata = QueueItemMetadata(
                item_id=document["item_id"],
                created_at=document["created_at"],
                added_by=document.get("added_by"),
                updated_at=document.get("updated_at"),
                tags=document.get("tags", []),
            )
            results.append((document["data"], metadata))

        return results


class QueueManager:
    """Manager for multiple queues.

    The QueueManager allows creating and accessing different queues
    stored in MongoDB collections.
    """

    def __init__(self, settings: QueueManagerSettings):
        """Initialize the QueueManager with the given settings.

        Args:
            settings: QueueManagerSettings object
        """
        self.settings = settings
        self._queues: Dict[str, AsyncIOMotorCollection] = {}

    def _get_collection_name(self, queue_name: str) -> str:
        """Get the collection name for a queue.

        Args:
            queue_name: The name of the queue

        Returns:
            The collection name
        """
        return f"{self.settings.collection_prefix}{queue_name}"

    def get_queue(self, queue_name: str = None, key: str = None) -> Queue:
        """Get a queue by name.

        Args:
            queue_name: The name of the queue (defaults to 'default')
            key: The key to identify items in this queue (defaults to settings.default_key)

        Returns:
            Queue object
        """
        from botspot.components.data.mongo_database import get_database

        queue_name = queue_name or "default"
        key = key or self.settings.default_key

        # Create the collection if it doesn't exist
        if queue_name not in self._queues:
            collection_name = self._get_collection_name(queue_name)
            self._queues[queue_name] = get_database()[collection_name]

            # Create indexes asynchronously
            asyncio.create_task(self._setup_indexes(queue_name))

        return Queue(self._queues[queue_name], key)

    async def _setup_indexes(self, queue_name: str):
        """Set up indexes for a queue collection.

        Args:
            queue_name: The name of the queue
        """
        collection = self._queues[queue_name]

        # Create indexes for efficient querying
        await collection.create_index([("queue_key", 1), ("created_at", 1)])
        await collection.create_index([("item_id", 1), ("queue_key", 1)], unique=True)
        await collection.create_index([("queue_key", 1), ("tags", 1)])

    async def get_all_queue_keys(self, queue_name: str = None) -> List[str]:
        """Get all queue keys in a collection.

        Args:
            queue_name: The name of the queue collection

        Returns:
            List of unique queue keys
        """
        queue_name = queue_name or "default"

        # Make sure the collection exists
        self.get_queue(queue_name)

        collection = self._queues[queue_name]
        keys = await collection.distinct("queue_key")
        return keys

    async def get_all_queue_stats(self, queue_name: str = None) -> Dict[str, QueueStats]:
        """Get statistics for all queues in a collection.

        Args:
            queue_name: The name of the queue collection

        Returns:
            Dictionary mapping queue keys to their stats
        """
        queue_name = queue_name or "default"
        keys = await self.get_all_queue_keys(queue_name)

        stats = {}
        for key in keys:
            queue = self.get_queue(queue_name, key)
            stats[key] = await queue.get_queue_stats()

        return stats


def setup_dispatcher(dp):
    """Set up the dispatcher with Queue Manager component handlers."""
    from aiogram import Router
    from aiogram.filters import Command
    from aiogram.types import Message

    router = Router(name="queue_manager")

    @router.message(Command("queue_stats"))
    async def queue_stats_command(message: Message):
        """Handler for /queue_stats command - shows queue statistics."""
        queue_manager = get_queue_manager()

        # Get the default queue stats
        default_queue = queue_manager.get_queue()
        stats = await default_queue.get_queue_stats()

        await message.reply(
            f"📊 **Queue Statistics**\n"
            f"Queue: {stats.queue_key}\n"
            f"Total items: {stats.total_items}\n"
            f"Oldest item: {stats.oldest_item_date or 'N/A'}\n"
            f"Newest item: {stats.newest_item_date or 'N/A'}"
        )

    dp.include_router(router)
    return dp


def initialize(settings: QueueManagerSettings) -> Optional[QueueManager]:
    """Initialize the Queue Manager component.

    Args:
        settings: QueueManagerSettings object

    Returns:
        QueueManager instance or None if disabled
    """
    if not settings.enabled:
        logger.info("Queue Manager component is disabled")
        return None

    logger.info("Initializing Queue Manager component")
    queue_manager = QueueManager(settings)

    return queue_manager


def get_queue_manager() -> QueueManager:
    """Get the Queue Manager from dependency manager.

    Returns:
        QueueManager instance
    """
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()

    if not hasattr(deps, "queue_manager"):
        raise RuntimeError("Queue Manager is not initialized")

    return deps.queue_manager
