from pydantic_settings import BaseSettings

from botspot.components.bot_commands_menu import BotCommandsMenuSettings
from botspot.components.error_handler import ErrorHandlerSettings
from botspot.components.event_scheduler import EventSchedulerSettings
from botspot.components.mongo_database import MongoDatabaseSettings
from botspot.components.print_bot_url import PrintBotUrlSettings
from botspot.components.trial_mode import TrialModeSettings


class NBLSettings(BaseSettings):
    """New Bot Library settings"""

    error_handling: ErrorHandlerSettings = ErrorHandlerSettings()
    mongo_database: MongoDatabaseSettings = MongoDatabaseSettings()
    print_bot_url: PrintBotUrlSettings = PrintBotUrlSettings()
    trial_mode: TrialModeSettings = TrialModeSettings()
    bot_commands_menu: BotCommandsMenuSettings = BotCommandsMenuSettings()
    event_scheduler: EventSchedulerSettings = EventSchedulerSettings()

    class Config:
        env_prefix = "NBL_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
