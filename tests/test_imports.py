def test_core_imports():
    from botspot.core.botspot_settings import BotspotSettings
    from botspot.core.dependency_manager import DependencyManager

    assert BotspotSettings
    assert DependencyManager


def test_components_imports():
    from botspot.components.ask_user_handler import AskUserSettings
    from botspot.components.bot_commands_menu import BotCommandsMenuSettings
    from botspot.components.error_handler import ErrorHandlerSettings
    from botspot.components.event_scheduler import EventSchedulerSettings
    from botspot.components.mongo_database import MongoDatabaseSettings
    from botspot.components.print_bot_url import PrintBotUrlSettings
    from botspot.components.trial_mode import TrialModeSettings

    assert AskUserSettings
    assert BotCommandsMenuSettings
    assert ErrorHandlerSettings
    assert EventSchedulerSettings
    assert MongoDatabaseSettings
    assert PrintBotUrlSettings
    assert TrialModeSettings


def test_utils_imports():
    from botspot.utils import send_safe, reply_safe, answer_safe
    from botspot.utils import get_user, get_name, get_message_text, strip_command

    assert send_safe
    assert reply_safe
    assert answer_safe
    assert get_user
    assert get_name
    assert get_message_text
    assert strip_command
