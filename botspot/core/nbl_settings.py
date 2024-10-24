from pydantic_settings import BaseSettings

from botspot.components.ask_user_handler import AskUserSettings
from botspot.components.bot_commands_menu import BotCommandsMenuSettings
from botspot.components.error_handler import ErrorHandlerSettings
from botspot.components.event_scheduler import EventSchedulerSettings
from botspot.components.mongo_database import MongoDatabaseSettings
from botspot.components.print_bot_url import PrintBotUrlSettings
from botspot.components.trial_mode import TrialModeSettings
from botspot.components.user_data import UserDataSettings


class NBLSettings(BaseSettings):
    """New Bot Library settings"""

    error_handling: ErrorHandlerSettings = ErrorHandlerSettings()
    mongo_database: MongoDatabaseSettings = MongoDatabaseSettings()
    print_bot_url: PrintBotUrlSettings = PrintBotUrlSettings()
    trial_mode: TrialModeSettings = TrialModeSettings()
    bot_commands_menu: BotCommandsMenuSettings = BotCommandsMenuSettings()
    event_scheduler: EventSchedulerSettings = EventSchedulerSettings()
    ask_user: AskUserSettings = AskUserSettings()
    user_data: UserDataSettings = UserDataSettings()

    class Config:
        env_prefix = "NBL_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
