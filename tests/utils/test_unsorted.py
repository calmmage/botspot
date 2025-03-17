import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from botspot.utils.unsorted import (
    get_user,
    get_name,
    get_message_text,
    _extract_message_text,
    strip_command,
)


class TestGetUser:
    def test_get_user_from_message(self):
        """Test getting username from message.from_user"""
        # Setup
        message = MagicMock()
        message.from_user.username = "test_user"
        message.from_user.id = 123456789
        message.forward_from = None
        
        # Execute
        result = get_user(message)
        
        # Verify
        assert result == "test_user"
        
    def test_get_user_id_when_no_username(self):
        """Test getting user ID when username is not set"""
        # Setup
        message = MagicMock()
        message.from_user.username = None
        message.from_user.id = 123456789
        message.forward_from = None
        
        # Execute
        result = get_user(message)
        
        # Verify
        assert result == 123456789
        
    def test_get_user_from_forward(self):
        """Test getting username from forwarded message"""
        # Setup
        message = MagicMock()
        message.from_user.username = "original_user"
        message.from_user.id = 123456789
        message.forward_from.username = "forward_user"
        message.forward_from.id = 987654321
        
        # Execute with forward_priority=True
        result = get_user(message, forward_priority=True)
        
        # Verify
        assert result == "forward_user"
        
    def test_get_user_id_from_forward_when_no_username(self):
        """Test getting user ID from forwarded message when username is not set"""
        # Setup
        message = MagicMock()
        message.from_user.username = "original_user"
        message.from_user.id = 123456789
        message.forward_from.username = None
        message.forward_from.id = 987654321
        
        # Execute with forward_priority=True
        result = get_user(message, forward_priority=True)
        
        # Verify
        assert result == 987654321


class TestGetName:
    def test_get_name_from_message(self):
        """Test getting full name from message.from_user"""
        # Setup
        message = MagicMock()
        message.from_user.full_name = "Test User"
        message.forward_from = None
        
        # Execute
        result = get_name(message)
        
        # Verify
        assert result == "Test User"
        
    def test_get_name_from_forward(self):
        """Test getting full name from forwarded message"""
        # Setup
        message = MagicMock()
        message.from_user.full_name = "Original User"
        message.forward_from.full_name = "Forward User"
        
        # Execute with forward_priority=True
        result = get_name(message, forward_priority=True)
        
        # Verify
        assert result == "Forward User"


class TestStripCommand:
    def test_strip_command_with_text(self):
        """Test stripping command from text with arguments"""
        # Execute
        result = strip_command("/command some arguments")
        
        # Verify
        assert result == "some arguments"
        
    def test_strip_command_without_text(self):
        """Test stripping command from text without arguments"""
        # Execute
        result = strip_command("/command")
        
        # Verify
        assert result == ""
        
    def test_strip_command_not_a_command(self):
        """Test stripping command from text that is not a command"""
        # Execute
        result = strip_command("This is not a command")
        
        # Verify
        assert result == "This is not a command"


class TestExtractMessageText:
    @pytest.mark.asyncio
    async def test_extract_message_text_with_text(self):
        """Test extracting text from message with text"""
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
        with patch("botspot.utils.unsorted._extract_message_text") as mock_extract:
            # Setup
            mock_extract.return_value = {
                "text": "Test message",
                "caption": "Test caption"
            }
            
            message = MagicMock()
            
            # Execute
            result = await get_message_text(message)
            
            # Verify
            assert result == "Test message\n\nTest caption"
            mock_extract.assert_called_once_with(message, False, False, as_dict=True)