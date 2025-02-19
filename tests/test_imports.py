def test_core_imports():
    from botspot.core.botspot_settings import BotspotSettings
    from botspot.core.dependency_manager import DependencyManager

    assert BotspotSettings
    assert DependencyManager


def test_components_imports():
    from botspot.components.data.mongo_database import MongoDatabaseSettings
    from botspot.components.features.user_interactions import AskUserSettings
    from botspot.components.main.event_scheduler import EventSchedulerSettings
    from botspot.components.main.trial_mode import TrialModeSettings
    from botspot.components.middlewares.error_handler import ErrorHandlerSettings
    from botspot.components.qol.bot_commands_menu import BotCommandsMenuSettings
    from botspot.components.qol.print_bot_url import PrintBotUrlSettings

    assert AskUserSettings
    assert BotCommandsMenuSettings
    assert ErrorHandlerSettings
    assert EventSchedulerSettings
    assert MongoDatabaseSettings
    assert PrintBotUrlSettings
    assert TrialModeSettings


def test_utils_imports():
    from botspot.utils import (
        answer_safe,
        get_message_text,
        get_name,
        get_user,
        reply_safe,
        send_safe,
        strip_command,
    )

    assert send_safe
    assert reply_safe
    assert answer_safe
    assert get_user
    assert get_name
    assert get_message_text
    assert strip_command
