from pydantic_settings import BaseSettings


class ChatFetcherSettings(BaseSettings):
    enabled: bool = False

    class Config:
        env_prefix = "BOTSPOT_CHAT_FETCHER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class ChatFetcher:
    pass


def setup_dispatcher(dp):
    return dp


def initialize(settings: ChatFetcherSettings) -> ChatFetcher:
    pass


def get_chat_fetcher() -> ChatFetcher:
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    return deps.chat_fetcher
