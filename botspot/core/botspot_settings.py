from functools import cached_property
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings

from botspot.components.data.mongo_database import MongoDatabaseSettings
from botspot.components.data.user_data import UserDataSettings
from botspot.components.features.user_interactions import AskUserSettings
from botspot.components.main.event_scheduler import EventSchedulerSettings
from botspot.components.main.single_user_mode import SingleUserModeSettings
from botspot.components.main.telethon_manager import TelethonManagerSettings
from botspot.components.main.trial_mode import TrialModeSettings
from botspot.components.middlewares.error_handler import ErrorHandlerSettings
from botspot.components.new.auto_archive import AutoArchiveSettings
from botspot.components.new.chat_binder import ChatBinderSettings
from botspot.components.new.chat_fetcher import ChatFetcherSettings
from botspot.components.new.llm_provider import LLMProviderSettings
from botspot.components.new.queue_manager import QueueManagerSettings
from botspot.components.new.s3_storage import S3StorageSettings
from botspot.components.qol.bot_commands_menu import BotCommandsMenuSettings
from botspot.components.qol.bot_info import BotInfoSettings
from botspot.components.qol.print_bot_url import PrintBotUrlSettings
from botspot.utils.admin_filter import AdminFilterSettings
from botspot.utils.send_safe import SendSafeSettings


class BotspotSettings(BaseSettings):
    debug: bool = Field(
        default=False,
        description="Enable debug mode",
    )

    admins_str: str = Field(
        default="",
        description="Comma-separated list of admin usernames (e.g., '@abc,@def')",
    )

    @cached_property
    def admins(self) -> List[str]:
        """Parse the comma-separated string of admin usernames into a list of strings."""
        if not self.admins_str:
            return []
        return [x.strip() for x in self.admins_str.split(",") if x.strip()]

    friends_str: str = Field(
        default="",
        description="Comma-separated list of friends usernames (e.g., '@abc,@def')",
    )

    @cached_property
    def friends(self) -> List[str]:
        """Parse the comma-separated string of friend usernames into a list of strings."""
        if not self.friends_str:
            return []
        return [x.strip() for x in self.friends_str.split(",") if x.strip()]

    ask_user: AskUserSettings = AskUserSettings()
    bot_commands_menu: BotCommandsMenuSettings = BotCommandsMenuSettings()
    bot_info: BotInfoSettings = BotInfoSettings()
    error_handling: ErrorHandlerSettings = ErrorHandlerSettings()
    event_scheduler: EventSchedulerSettings = EventSchedulerSettings()
    mongo_database: MongoDatabaseSettings = MongoDatabaseSettings()
    print_bot_url: PrintBotUrlSettings = PrintBotUrlSettings()
    telethon_manager: TelethonManagerSettings = TelethonManagerSettings()
    trial_mode: TrialModeSettings = TrialModeSettings()
    user_data: UserDataSettings = UserDataSettings()
    single_user_mode: SingleUserModeSettings = SingleUserModeSettings()
    send_safe: SendSafeSettings = SendSafeSettings()
    admin_filter: AdminFilterSettings = AdminFilterSettings()
    chat_binder: ChatBinderSettings = ChatBinderSettings()
    chat_fetcher: ChatFetcherSettings = ChatFetcherSettings()
    llm_provider: LLMProviderSettings = LLMProviderSettings()
    queue_manager: QueueManagerSettings = QueueManagerSettings()
    auto_archive: AutoArchiveSettings = AutoArchiveSettings()
    s3_storage: S3StorageSettings = S3StorageSettings()

    class Config:
        env_prefix = "BOTSPOT_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
