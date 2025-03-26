from botspot.utils.internal import get_logger

logger = get_logger()

from datetime import datetime
from typing import List, Optional, Type

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


class Queue:
    def __init__(
        self,
        key: str,
        item_model: Type[BaseModel],
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
            projection["username"] = 0
        return projection

    def enrich_item(self, item: BaseModel, username: Optional[str] = None) -> dict:
        doc = item.model_dump()
        doc["queue_id"] = self.key
        if self.use_timestamp:
            doc["timestamp"] = datetime.now()
        if self.use_priority:
            doc["priority"] = 0
        if self.use_done:
            doc["done"] = False
        if username:
            doc["username"] = username
        return doc

    async def add_item(self, item: BaseModel, username: Optional[str] = None):
        if not self.single_user_mode and username is None:
            raise ValueError("username is required unless single_user_mode is enabled")
        doc = self.enrich_item(item, username)
        await self.collection.insert_one(doc)

    async def get_items(
        self,
        username: Optional[str] = None,
        limit: Optional[int] = None,
        provide_all_fields: bool = False,
    ) -> List[dict]:
        if not self.single_user_mode and username is None:
            raise ValueError("username is required unless single_user_mode is enabled")
        query = {"queue_id": self.key}
        if username:
            query["username"] = username
        projection = None if provide_all_fields else self.projection
        cursor = self.collection.find(query, projection=projection)
        if limit is not None:
            cursor = cursor.limit(limit)
        items = await cursor.to_list(length=limit)
        return items


class QueueManager:
    def __init__(self, settings: QueueManagerSettings, single_user_mode: Optional[bool] = None):
        from botspot.utils.deps_getters import get_database

        self.settings = settings
        self.db = get_database()  # Fetch MongoDB database instance
        self.queues = {}
        if single_user_mode is None:
            from botspot.core.dependency_manager import get_dependency_manager

            single_user_mode = not self.settings.enabled
        self.single_user_mode = single_user_mode

    def create_queue(
        self,
        key: str = "default",
        item_model: Type[BaseModel] = QueueItem,
        use_timestamp: bool = True,
        use_priority: bool = False,
        use_done: bool = False,
        collection=None,
    ) -> Queue:

        if collection is None:
            collection_name = f"{self.settings.collection_name_prefix}queues"
            collection = self.db[collection_name]

        queue = Queue(
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
            raise KeyError(f"Queue with key '{key}' does not exist")
        return self.queues[key]


def get_queue_manager() -> QueueManager:
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    return deps.queue_manager


def create_queue(key: str = "default", item_model: Type[BaseModel] = QueueItem) -> Queue:
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
        raise RuntimeError("MongoDB is required for queue_manager component")

    single_user_mode = deps.botspot_settings.single_user_mode.enabled
    return QueueManager(settings, single_user_mode=single_user_mode)
