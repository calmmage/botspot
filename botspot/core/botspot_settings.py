from pydantic_settings import BaseSettings

from botspot.components.ask_user_handler import AskUserSettings
from botspot.components.bot_commands_menu import BotCommandsMenuSettings
from botspot.components.bot_info import BotInfoSettings
from botspot.components.error_handler import ErrorHandlerSettings
from botspot.components.event_scheduler import EventSchedulerSettings
from botspot.components.mongo_database import MongoDatabaseSettings
from botspot.components.print_bot_url import PrintBotUrlSettings
from botspot.components.trial_mode import TrialModeSettings


class BotspotSettings(BaseSettings):
    """New Bot Library settings"""

    error_handling: ErrorHandlerSettings = ErrorHandlerSettings()
    mongo_database: MongoDatabaseSettings = MongoDatabaseSettings()
    print_bot_url: PrintBotUrlSettings = PrintBotUrlSettings()
    trial_mode: TrialModeSettings = TrialModeSettings()
    bot_commands_menu: BotCommandsMenuSettings = BotCommandsMenuSettings()
    event_scheduler: EventSchedulerSettings = EventSchedulerSettings()
    ask_user: AskUserSettings = AskUserSettings()
    bot_info: BotInfoSettings = BotInfoSettings()

    class Config:
        env_prefix = "BOTSPOT_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
