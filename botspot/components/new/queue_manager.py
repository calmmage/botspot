from botspot.utils.internal import get_logger

logger = get_logger()

from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from pydantic import BaseModel
from pydantic_settings import BaseSettings

# Placeholder for database connection (adjust as needed)


class QueueManagerSettings(BaseSettings):
    enabled: bool = False
    collection_name_prefix: str = "botspot_queue_"

    class Config:
        env_prefix = "BOTSPOT_QUEUE_MANAGER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class QueueItem(BaseModel):
    data: str

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


T = TypeVar("T", bound=QueueItem)


class Queue(Generic[T]):
    def __init__(
        self,
        key: str,
        item_model: Type[T],
        collection,
        use_timestamp: bool = True,
        use_priority: bool = False,
        use_done: bool = False,
        single_user_mode: bool = False,
    ):
        self.key = key
        self.item_model = item_model
        self.collection = collection

        self.use_timestamp = use_timestamp
        self.use_priority = use_priority
        self.use_done = use_done

        self.single_user_mode = single_user_mode

    @property
    def projection(self):
        projection = {"_id": 0}
        if not self.use_timestamp:
            projection["timestamp"] = 0
        if not self.use_priority:
            projection["priority"] = 0
        if not self.use_done:
            projection["done"] = 0
        if not self.single_user_mode:
            projection["user_id"] = 0
        return projection

    def enrich_item(self, item: T, user_id: Optional[int] = None) -> dict:
        doc = item.model_dump()
        # doc["queue_id"] = self.key
        if self.use_timestamp:
            doc["timestamp"] = datetime.now()
        if self.use_priority:
            doc["priority"] = 0
        if self.use_done:
            doc["done"] = False
        if user_id:
            doc["user_id"] = user_id
        return doc

    async def add_item(self, item: T, user_id: Optional[int] = None):
        if not self.single_user_mode and user_id is None:
            from botspot.core.errors import QueuePermissionError

            raise QueuePermissionError("user_id is required unless single_user_mode is enabled")
        doc = self.enrich_item(item, user_id)
        await self.collection.insert_one(doc)

    async def get_items(
        self,
        user_id: Optional[int] = None,
        limit: Optional[int] = None,
        provide_all_fields: bool = False,
    ) -> List[T]:
        if not self.single_user_mode and user_id is None:
            from botspot.core.errors import QueuePermissionError

            raise QueuePermissionError("user_id is required unless single_user_mode is enabled")
        query = {}
        if user_id:
            query["user_id"] = user_id
        projection = None if provide_all_fields else self.projection
        cursor = self.collection.find(query, projection=projection)
        if limit is not None:
            cursor = cursor.limit(limit)
        items = await cursor.to_list(length=limit)
        return [self.item_model.model_validate(item) for item in items]

    async def get_records(
        self, user_id: Optional[int] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        if not self.single_user_mode and user_id is None:
            from botspot.core.errors import QueuePermissionError

            raise QueuePermissionError("user_id is required unless single_user_mode is enabled")
        query = {}
        if user_id:
            query["user_id"] = user_id
        cursor = self.collection.find(query)
        if limit is not None:
            cursor = cursor.limit(limit)
        return await cursor.to_list(length=limit)


class QueueManager:
    def __init__(self, settings: QueueManagerSettings, single_user_mode: Optional[bool] = None):
        from botspot.utils.deps_getters import get_database

        self.settings = settings
        self.db = get_database()  # Fetch MongoDB database instance
        self.queues: Dict[str, Queue] = {}
        if single_user_mode is None:
            from botspot.core.dependency_manager import get_dependency_manager

            single_user_mode = not self.settings.enabled
        self.single_user_mode = single_user_mode

    def create_queue(
        self,
        key: str = "default",
        item_model: Type[T] = QueueItem,  # type: ignore
        use_timestamp: bool = True,
        use_priority: bool = False,
        use_done: bool = False,
        collection=None,
    ) -> Queue[T]:
        if collection is None:
            collection_name = f"{self.settings.collection_name_prefix}{key}"
            collection = self.db[collection_name]

        queue: Queue[T] = Queue(
            key=key,
            item_model=item_model,
            collection=collection,
            use_timestamp=use_timestamp,
            use_priority=use_priority,
            use_done=use_done,
            single_user_mode=self.single_user_mode,
        )
        self.queues[key] = queue
        return queue

    def get_queue(self, key: str = "default") -> Queue:
        if key not in self.queues:
            from botspot.core.errors import QueueNotFoundError

            raise QueueNotFoundError(f"Queue with key '{key}' does not exist")
        return self.queues[key]


def get_queue_manager() -> QueueManager:
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    return deps.queue_manager


TItem = TypeVar("TItem", bound=BaseModel)


def create_queue(
    key: str = "default",
    item_model: Type[TItem] = QueueItem,  # type: ignore
) -> Queue[TItem]:
    qm = get_queue_manager()
    return qm.create_queue(key, item_model)


def get_queue(key: str = "default") -> Queue:
    qm = get_queue_manager()
    return qm.get_queue(key)


def setup_dispatcher(dp):
    """Setup dispatcher with queue management commands."""
    return dp


def initialize(settings: QueueManagerSettings) -> QueueManager:
    """Initialize the queue manager component."""
    from botspot.core.dependency_manager import get_dependency_manager

    # Check that MongoDB is available
    deps = get_dependency_manager()
    if not deps.botspot_settings.mongo_database.enabled:
        from botspot.core.errors import ConfigurationError

        raise ConfigurationError("MongoDB is required for queue_manager component")

    single_user_mode = deps.botspot_settings.single_user_mode.enabled
    return QueueManager(settings, single_user_mode=single_user_mode)


if __name__ == "__main__":
    import asyncio
    from enum import Enum

    from aiogram.types import Message

    from botspot.utils.send_safe import send_safe

    # Example 1: Basic message handler adding text to queue
    async def message_handler(message: Message):
        queue = create_queue()
        item = QueueItem(data=message.text)
        await queue.add_item(item, user_id=message.from_user.id)

        items = await queue.get_items(user_id=message.from_user.id)
        await send_safe(message.chat.id, f"Added to queue! Total items: {len(items)}")

    # Example 2: Custom queue with specialized item model
    class MovieIdeaType(str, Enum):
        specific_movie = "specific_movie"
        cue = "cue"
        person = "person"

    class MovieIdea(BaseModel):
        idea: str
        type: MovieIdeaType

    async def movie_idea_handler(message: Message):
        movie_queue = create_queue("movies", MovieIdea)
        item = MovieIdea(idea="Inception", type=MovieIdeaType.specific_movie)
        await movie_queue.add_item(item, user_id=message.from_user.id)

    # Run examples with mock message
    asyncio.run(
        message_handler(Message(chat={"id": 123456}, text="Sample item", from_user={"id": 12345}))
    )
