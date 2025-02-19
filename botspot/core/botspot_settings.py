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
from botspot.utils.send_safe import SendSafeSettings


class BotspotSettings(BaseSettings):
    """New Bot Library settings"""

    # noinspection PyDataclass
    admins: list[int] = Field(
        default_factory=list,
        description="Default admin",
        json_schema_extra={"format": "comma_separated"},
    )
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

    class Config:
        env_prefix = "BOTSPOT_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
