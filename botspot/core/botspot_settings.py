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
from botspot.components.qol.bot_commands_menu import BotCommandsMenuSettings
from botspot.components.qol.bot_info import BotInfoSettings
from botspot.components.qol.print_bot_url import PrintBotUrlSettings
from botspot.utils.admin_filter import AdminFilterSettings
from botspot.utils.send_safe import SendSafeSettings

from functools import cached_property
from typing import List

class BotspotSettings(BaseSettings):
    admins_str: str = Field(
        default="",
        description="Comma-separated list of admin usernames (e.g., '@abc,@def')"
    )

    @cached_property
    def admins(self) -> List[str]:
        """Parse the comma-separated string of admin usernames into a list of strings."""
        if not self.admins_str:
            return []
        return [x.strip() for x in self.admins_str.split(',') if x.strip()]

    
    friends_str: str = Field(
        default="",
        description="Comma-separated list of friends usernames (e.g., '@abc,@def')"
    )

    @cached_property
    def friends(self) -> List[str]:
        """Parse the comma-separated string of friend usernames into a list of strings."""
        if not self.friends_str:
            return []
        return [x.strip() for x in self.friends_str.split(',') if x.strip()]




    # noinspection PyDataclass
    friends: list[str] = Field(
        default_factory=list,
        description="List of friend user IDs",
        json_schema_extra={"format": "comma_separated"},
    )

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

    class Config:
        env_prefix = "BOTSPOT_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
