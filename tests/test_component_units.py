"""Component behaviour that does not need a full dispatcher, still without MagicMock theater."""

import pytest

from botspot.components.middlewares.i18n import get_lang, register_strings, set_lang, t
from botspot.components.new.auto_archive import AutoArchive, AutoArchiveSettings, CommandFilterMode
from botspot.components.new.llm_provider import (
    MODEL_NAME_SHORTCUTS,
    LLMProvider,
    LLMProviderSettings,
    initialize as llm_initialize,
)
from botspot.components.new.s3_storage import S3StorageSettings, initialize as s3_initialize
from botspot.core.errors import BotspotError, ChatBindingExistsError
from botspot.utils.easter_eggs import easter_eggs, get_easter_egg, get_pong, pongs
from tests.telegram import make_message


class TestI18n:
    def test_missing_key_returns_the_key(self):
        assert t("definitely.not.a.key") == "definitely.not.a.key"

    def test_russian_and_english_and_format(self):
        set_lang("en")
        assert "Oops" in t("error_handler.something_went_wrong")
        set_lang("ru")
        assert "Упс" in t("error_handler.something_went_wrong")
        set_lang("en")
        assert "alice" in t("access_control.add_friend_success", username="alice")

    def test_register_strings_and_get_lang(self):
        register_strings({"app.hello": {"en": "hi {name}", "ru": "прив {name}"}})
        set_lang("ru")
        assert t("app.hello", name="петр") == "прив петр"
        assert get_lang() == "ru"
        set_lang("en")


class TestAutoArchiveCommandFilter:
    def test_pure_commands_only_match_slash_with_no_args(self):
        aa = AutoArchive(AutoArchiveSettings(command_filter_mode=CommandFilterMode.PURE_COMMANDS))
        assert aa._is_filtered_command(make_message("/start"))
        assert not aa._is_filtered_command(make_message("/start extra"))
        assert not aa._is_filtered_command(make_message("hello"))

    def test_single_line_and_all_commands(self):
        single = AutoArchive(AutoArchiveSettings(command_filter_mode=CommandFilterMode.SINGLE_LINE))
        assert single._is_filtered_command(make_message("/start extra"))
        assert not single._is_filtered_command(make_message("/start\nmore"))

        all_cmds = AutoArchive(
            AutoArchiveSettings(command_filter_mode=CommandFilterMode.ALL_COMMANDS)
        )
        assert all_cmds._is_filtered_command(make_message("/start\nmore"))


class TestLLMProvider:
    def test_initialize_disabled_is_none(self):
        assert llm_initialize(LLMProviderSettings(enabled=False)) is None

    def test_shortcut_expands_and_full_names_pass_through(self):
        provider = LLMProvider(LLMProviderSettings(enabled=True, skip_import_check=True))
        assert provider._get_full_model_name("claude-4") == MODEL_NAME_SHORTCUTS["claude-4"]
        assert (
            provider._get_full_model_name("anthropic/claude-sonnet-4-5")
            == "anthropic/claude-sonnet-4-5"
        )
        assert provider._get_full_model_name("totally-unknown") == "totally-unknown"

    @pytest.mark.asyncio
    async def test_prepare_messages_with_system_and_bytes_attachment(self):
        provider = LLMProvider(LLMProviderSettings(enabled=True, skip_import_check=True))
        messages = await provider._aprepare_messages(
            "describe this",
            system_message="you are brief",
            attachments=[b"\x89PNG"],
        )
        assert messages[0] == {"role": "system", "content": "you are brief"}
        content = messages[1]["content"]
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "image_url"


class TestS3:
    def test_initialize_disabled_is_none(self):
        assert s3_initialize(S3StorageSettings(enabled=False)) is None


class TestErrorsAndEasterEggs:
    def test_botspot_error_keeps_message_off_str(self):
        err = ChatBindingExistsError("already bound", user_message="try another key")
        assert err.message == "already bound"
        assert err.user_message == "try another key"
        assert str(err) == ""
        assert isinstance(err, BotspotError)

    def test_easter_eggs_and_pongs_are_non_empty(self):
        assert easter_eggs
        assert pongs
        assert get_easter_egg() in easter_eggs
        assert get_pong() in pongs
