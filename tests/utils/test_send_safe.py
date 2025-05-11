from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import BufferedInputFile, Chat, Message

from botspot.utils.send_safe import (
    SendSafeSettings,
    _send_with_parse_mode_fallback,
    answer_safe,
    reply_safe,
    send_safe,
)


@pytest.fixture
def mock_bot():
    bot = AsyncMock(spec=Bot)
    bot.send_message = AsyncMock(return_value=MagicMock(spec=Message))
    bot.send_document = AsyncMock(return_value=MagicMock(spec=Message))
    return bot


@pytest.fixture
def mock_deps(mock_bot):
    deps = MagicMock()
    deps.bot = mock_bot

    # Mock settings
    settings = MagicMock()
    settings.send_safe = SendSafeSettings()
    deps.botspot_settings = settings

    return deps


@pytest.fixture
def mock_message():
    message = MagicMock(spec=Message)
    message.message_id = 12345
    message.chat = MagicMock(spec=Chat)
    message.chat.id = 67890
    return message


class TestSendWithParseModeCallback:
    @pytest.mark.asyncio
    async def test_successful_send(self, mock_bot):
        """Test successful message sending with parse mode"""
        chat_id = 12345
        text = "Test message"

        await _send_with_parse_mode_fallback(mock_bot, chat_id, text, parse_mode=ParseMode.HTML)

        mock_bot.send_message.assert_called_once_with(chat_id, text, parse_mode=ParseMode.HTML)

    @pytest.mark.asyncio
    async def test_fallback_on_error(self, mock_bot):
        """Test fallback to plain text when parsing fails"""
        chat_id = 12345
        text = "Test message with <b>invalid HTML"

        # First call raises exception, second call succeeds
        mock_bot.send_message.side_effect = [
            Exception("Parse error"),
            MagicMock(spec=Message),
        ]

        await _send_with_parse_mode_fallback(mock_bot, chat_id, text, parse_mode=ParseMode.HTML)

        # Check that it was called twice
        assert mock_bot.send_message.call_count == 2

        # The second call should have no parse mode
        assert mock_bot.send_message.call_args_list[1][0] == (chat_id, text)
        assert mock_bot.send_message.call_args_list[1][1].get("parse_mode") is None


class TestSendSafe:
    @pytest.mark.asyncio
    async def test_basic_send(self, mock_deps):
        """Test basic message sending"""
        chat_id = 12345
        text = "Test message"

        await send_safe(chat_id, text, deps=mock_deps)

        mock_deps.bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_wrap_text(self, mock_deps):
        """Test text wrapping option"""
        chat_id = 12345
        text = "A very long line that should be wrapped according to settings"

        # Enable wrapping
        mock_deps.botspot_settings.send_safe.wrap_text = True
        mock_deps.botspot_settings.send_safe.wrap_width = 20

        await send_safe(chat_id, text, deps=mock_deps)

        # Check that the text was wrapped
        sent_text = mock_deps.bot.send_message.call_args[0][1]
        assert len(max(sent_text.split("\n"), key=len)) <= 20

    @pytest.mark.asyncio
    async def test_long_message_as_file(self, mock_deps):
        """Test sending long messages as files"""
        chat_id = 12345
        text = "A" * 5000  # Create a message longer than MAX_TELEGRAM_MESSAGE_LENGTH

        # Enable sending long messages as files
        mock_deps.botspot_settings.send_safe.send_long_messages_as_files = True

        await send_safe(chat_id, text, deps=mock_deps)

        # Check that send_document was called instead of send_message
        mock_deps.bot.send_document.assert_called_once()

        # Verify the document is a BufferedInputFile with the correct content
        file_arg = mock_deps.bot.send_document.call_args[0][1]
        assert isinstance(file_arg, BufferedInputFile)
        assert file_arg.filename is not None and file_arg.filename.endswith(".txt")

    @pytest.mark.asyncio
    async def test_long_message_split(self, mock_deps):
        """Test splitting long messages instead of sending as file"""
        chat_id = 12345
        text = "A" * 5000  # Create a message longer than MAX_TELEGRAM_MESSAGE_LENGTH

        # Disable sending long messages as files
        mock_deps.botspot_settings.send_safe.send_long_messages_as_files = False

        await send_safe(chat_id, text, deps=mock_deps)

        # Check that send_message was called multiple times
        assert mock_deps.bot.send_message.call_count > 1

    @pytest.mark.asyncio
    async def test_message_as_chat_id(self, mock_deps, mock_message):
        """Test using a Message object as chat_id"""
        text = "Test message"

        await send_safe(mock_message, text, deps=mock_deps)

        # Check that the message was sent to the chat id and replied to the message
        call_args = mock_deps.bot.send_message.call_args
        assert call_args[0][0] == mock_message.chat.id
        assert call_args[1].get("reply_to_message_id") == mock_message.message_id


class TestReplySafe:
    @pytest.mark.asyncio
    @patch("botspot.utils.send_safe.send_safe")
    async def test_reply_safe(self, mock_send_safe, mock_message):
        """Test reply_safe function"""
        text = "Test reply"

        await reply_safe(mock_message, text)

        # Check that send_safe was called with correct parameters
        mock_send_safe.assert_called_once_with(
            mock_message.chat.id,
            text,
            deps=None,
            reply_to_message_id=mock_message.message_id,
            filename=None,
            escape_markdown=False,
            wrap=None,
            parse_mode=None,
            cleanup=None,
            cleanup_timeout=None,
        )


class TestAnswerSafe:
    @pytest.mark.asyncio
    @patch("botspot.utils.send_safe.send_safe")
    async def test_answer_safe(self, mock_send_safe, mock_message):
        """Test answer_safe function"""
        text = "Test answer"

        await answer_safe(mock_message, text)

        # Check that send_safe was called with correct parameters
        mock_send_safe.assert_called_once_with(
            mock_message.chat.id,
            text,
            deps=None,
            filename=None,
            escape_markdown=False,
            wrap=None,
            parse_mode=None,
            cleanup=None,
            cleanup_timeout=None,
        )
