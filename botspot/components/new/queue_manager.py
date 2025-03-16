"""
Idea: I want a simple way to create a queue object on top of my database

- Similar to /bind command the default key is "default"
- 

Options:
Option 1: make a class Queue that 
Option 2: make a clsas QueueManager that has 



"""

from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger

logger = get_logger()


class QueueManagerSettings(BaseSettings):
    enabled: bool = False
    collection_prefix: str = "queue_"

    class Config:
        env_prefix = "BOTSPOT_QUEUE_MANAGER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class QueueManager:
    pass


def setup_dispatcher(dp):
    return dp


def initialize(settings: QueueManagerSettings) -> QueueManager:
    pass


def get_queue_manager() -> QueueManager:
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    return deps.queue_manager
