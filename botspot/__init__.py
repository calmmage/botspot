from importlib.metadata import PackageNotFoundError

try:
    import importlib.metadata

    __version__ = importlib.metadata.version(__package__ or __name__)
    del importlib
except PackageNotFoundError:
    import toml
    from pathlib import Path

    path = Path(__file__).parent.parent / "pyproject.toml"
    __version__ = toml.load(path)["project"]["version"]
    del toml, Path, path

from . import commands_menu, llm_provider, trial_mode, user_data, user_interactions
from .components.data import mongo_database
from .components.features import multi_forward_handler
from .components.main import event_scheduler, single_user_mode, telethon_manager
from .components.main.single_user_mode import get_single_user, is_single_user_mode_enabled
from .components.middlewares import error_handler
from .components.new import chat_fetcher, llm_provider
from .components.qol import bot_commands_menu, bot_info, print_bot_url
from .core import get_dependency_manager
from .utils import (
    answer_safe,
    compare_users,
    get_bot,
    get_chat_fetcher,
    get_database,
    get_dispatcher,
    get_easter_egg,
    get_llm_provider,
    get_message_text,
    get_name,
    get_pong,
    get_scheduler,
    get_telethon_client,
    get_telethon_manager,
    get_user,
    get_user_manager,
    is_admin,
    is_friend,
    reply_safe,
    send_safe,
    strip_command,
    to_user_record,
)

__all__ = [
    # files
    "trial_mode",
    "user_interactions",
    "user_data",
    "get_user_manager",
    "commands_menu",
    "__version__",
    # key features
    # components
    ##  settings
    # "bot_commands_menu",
    # "bot_info",
    ## middlewares
    "error_handler",
    "event_scheduler",
    ## data
    "mongo_database",
    # no need to expose
    ## main
    # "single_user_mode",
    ## utils
    # "print_bot_url",
    # has getters
    "telethon_manager",
    "get_telethon_manager",
    # LLM Provider
    "get_llm_provider",
    "llm_provider",
    # Chat Fetcher
    "chat_fetcher",
    "get_chat_fetcher",
    # utils
    "get_dependency_manager",
    "get_bot",
    "get_database",
    "get_scheduler",
    "get_telethon_client",
    "get_dispatcher",
    "answer_safe",
    "reply_safe",
    "send_safe",
    "get_message_text",
    "get_name",
    "get_user",
    "strip_command",
    "compare_users",
    "is_admin",
    "is_friend",
    "to_user_record",
    "get_easter_egg",
    "get_pong",
    "is_single_user_mode_enabled",
    "get_single_user",
]
