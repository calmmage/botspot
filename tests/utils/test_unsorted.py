from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.enums import ChatAction


class TestGetUser:
    def test_get_user_from_message(self):
        from botspot.utils.unsorted import get_user
        from tests.telegram import make_message

        assert get_user(make_message("hi", username="test_user")) == "test_user"

    def test_get_user_id_when_no_username(self):
        from botspot.utils.unsorted import get_user
        from tests.telegram import make_message

        assert get_user(make_message("hi", username=None, user_id=123456789)) == "123456789"

    def test_get_user_from_forward(self):
        from botspot.utils.unsorted import get_user
        from tests.telegram import make_message, make_user

        message = make_message(
            "hi",
            username="original_user",
            forward_from=make_user(user_id=987654321, username="forward_user"),
        )
        assert get_user(message, forward_priority=True) == "forward_user"

    def test_get_user_id_from_forward_when_no_username(self):
        from botspot.utils.unsorted import get_user
        from tests.telegram import make_message, make_user

        message = make_message(
            "hi",
            username="original_user",
            forward_from=make_user(user_id=987654321, username=None),
        )
        assert get_user(message, forward_priority=True) == "987654321"


class TestGetName:
    def test_get_name_from_message(self):
        from botspot.utils.unsorted import get_name
        from tests.telegram import make_message

        assert get_name(make_message("hi", first_name="Test", last_name="User")) == "Test User"

    def test_get_name_from_forward(self):
        from botspot.utils.unsorted import get_name
        from tests.telegram import make_message, make_user

        message = make_message(
            "hi",
            first_name="Original",
            last_name="User",
            forward_from=make_user(
                user_id=2, username="fwd", first_name="Forward", last_name="User"
            ),
        )
        assert get_name(message, forward_priority=True) == "Forward User"


class TestStripCommand:
    def test_strip_command_with_text(self):
        """Test stripping command from text with arguments"""
        from botspot.utils.unsorted import strip_command

        # Execute
        result = strip_command("/command some arguments")

        # Verify
        assert result == "some arguments"

    def test_strip_command_without_text(self):
        """Test stripping command from text without arguments"""
        from botspot.utils.unsorted import strip_command

        # Execute
        result = strip_command("/command")

        # Verify
        assert result == ""

    def test_strip_command_not_a_command(self):
        """Test stripping command from text that is not a command"""
        from botspot.utils.unsorted import strip_command

        # Execute
        result = strip_command("This is not a command")

        # Verify
        assert result == "This is not a command"


class TestExtractMessageText:
    @pytest.mark.asyncio
    async def test_extract_message_text_with_text(self):
        """Test extracting text from message with text"""
        from botspot.utils.unsorted import _extract_message_text

        # Setup
        message = MagicMock()
        message.text = "Test message"
        message.md_text = "*Test* message"
        message.caption = None
        message.document = None
        message.reply_to_message = None

        # Execute
        result = await _extract_message_text(message)

        # Verify
        assert result == "Test message"

    @pytest.mark.asyncio
    async def test_extract_message_text_with_markdown(self):
        """Test extracting text with markdown formatting"""
        from botspot.utils.unsorted import _extract_message_text

        # Setup
        message = MagicMock()
        message.text = "Test message"
        message.md_text = "*Test* message"
        message.caption = None
        message.document = None
        message.reply_to_message = None

        # Execute
        result = await _extract_message_text(message, as_markdown=True)

        # Verify
        assert result == "*Test* message"

    @pytest.mark.asyncio
    async def test_extract_message_text_with_caption(self):
        """Test extracting text from message with caption"""
        from botspot.utils.unsorted import _extract_message_text

        # Setup
        message = MagicMock()
        message.text = None
        message.caption = "Test caption"
        message.document = None
        message.reply_to_message = None

        # Execute
        result = await _extract_message_text(message)

        # Verify
        assert result == "Test caption"

    @pytest.mark.asyncio
    async def test_extract_message_text_with_document(self):
        """Test extracting text from message with document"""
        from botspot.utils.unsorted import _extract_message_text

        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Setup
            mock_deps = MagicMock()
            mock_bot = MagicMock()
            mock_file = MagicMock()
            mock_file.read.return_value = b"Test document content"
            mock_bot.download = AsyncMock(return_value=mock_file)
            mock_deps.bot = mock_bot
            mock_get_deps.return_value = mock_deps

            message = MagicMock()
            message.text = None
            message.caption = None
            message.document.mime_type = "text/plain"
            message.document.file_id = "file123"
            message.document.file_name = "test.txt"
            message.reply_to_message = None

            # Execute
            result = await _extract_message_text(message)

            # Verify
            assert result == "\n\nTest document content"
            mock_bot.download.assert_called_once_with("file123")

    @pytest.mark.asyncio
    async def test_extract_message_text_with_reply(self):
        """Test extracting text from message with reply"""
        from botspot.utils.unsorted import _extract_message_text

        # Setup
        reply_message = MagicMock()
        reply_message.text = "Reply message"
        reply_message.caption = None
        reply_message.document = None
        reply_message.reply_to_message = None

        message = MagicMock()
        message.text = "Test message"
        message.caption = None
        message.document = None
        message.reply_to_message = reply_message

        # Execute
        result = await _extract_message_text(message, include_reply=True)

        # Verify
        assert result == "Test message\n\n\n\nReply message"

    @pytest.mark.asyncio
    async def test_extract_message_text_as_dict(self):
        """Test extracting text as dictionary"""
        from botspot.utils.unsorted import _extract_message_text

        # Setup
        message = MagicMock()
        message.text = "Test message"
        message.caption = "Test caption"
        message.document = None
        message.reply_to_message = None

        # Execute
        result = await _extract_message_text(message, as_dict=True)

        # Verify
        assert isinstance(result, dict)
        assert result["text"] == "Test message"
        assert result["caption"] == "Test caption"


class TestGetMessageText:
    @pytest.mark.asyncio
    async def test_get_message_text(self):
        """Test getting message text"""
        from botspot.utils.unsorted import get_message_text

        with patch("botspot.utils.unsorted._extract_message_text") as mock_extract:
            # Setup
            mock_extract.return_value = {"text": "Test message", "caption": "Test caption"}

            message = MagicMock()

            # Execute
            result = await get_message_text(message)

            # Verify
            assert result == "Test message\n\nTest caption"
            mock_extract.assert_called_once_with(message, False, False, as_dict=True)


class TestSendTypingStatus:
    @pytest.mark.asyncio
    async def test_send_typing_status_default(self):
        """Test sending typing status with default action"""
        from botspot.utils.unsorted import send_typing_status

        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Setup
            mock_deps = MagicMock()
            mock_bot = AsyncMock()
            mock_deps.bot = mock_bot
            mock_get_deps.return_value = mock_deps

            message = MagicMock()
            message.chat.id = 123456789

            # Execute
            await send_typing_status(message)

            # Verify
            mock_bot.send_chat_action.assert_called_once_with(
                chat_id=123456789, action=ChatAction.TYPING
            )

    @pytest.mark.asyncio
    async def test_send_typing_status_custom_action(self):
        """Test sending typing status with custom action"""
        from botspot.utils.unsorted import send_typing_status

        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Setup
            mock_deps = MagicMock()
            mock_bot = AsyncMock()
            mock_deps.bot = mock_bot
            mock_get_deps.return_value = mock_deps

            message = MagicMock()
            message.chat.id = 123456789

            # Execute
            await send_typing_status(message, "upload_document")

            # Verify
            mock_bot.send_chat_action.assert_called_once_with(
                chat_id=123456789, action=ChatAction.UPLOAD_DOCUMENT
            )

    @pytest.mark.asyncio
    async def test_send_typing_status_invalid_action(self):
        """Test sending typing status with invalid action falls back to typing"""
        from botspot.utils.unsorted import send_typing_status

        with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
            # Setup
            mock_deps = MagicMock()
            mock_bot = AsyncMock()
            mock_deps.bot = mock_bot
            mock_get_deps.return_value = mock_deps

            message = MagicMock()
            message.chat.id = 123456789

            # Execute
            await send_typing_status(message, "invalid_action")

            # Verify
            mock_bot.send_chat_action.assert_called_once_with(
                chat_id=123456789, action=ChatAction.TYPING
            )
