from botspot.utils.text_utils import MAX_TELEGRAM_MESSAGE_LENGTH, escape_md, split_long_message


class TestEscapeMd:
    def test_escape_special_characters(self):
        """Test that all special characters are escaped"""
        text = "Hello _*[]()~`>#+-=|{}.! World"
        escaped = escape_md(text)

        # Each special character should be preceded by a backslash
        assert escaped == r"Hello \_\*\[\]\(\)\~\`\>\#\+\-\=\|\{\}\.\! World"

    def test_escape_non_special_characters(self):
        """Test that non-special characters are not escaped"""
        text = "Hello world 123"
        escaped = escape_md(text)

        # Text should remain unchanged
        assert escaped == text

    def test_escape_empty_string(self):
        """Test escaping an empty string"""
        assert escape_md("") == ""

    def test_escape_none_value(self):
        """Test that None is converted to string and escaped"""
        assert escape_md(None) == "None"


class TestSplitLongMessage:
    def test_short_message(self):
        """Test that short messages are not split"""
        text = "This is a short message"
        chunks = split_long_message(text)

        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_message_split_on_newline(self):
        """Test that long messages are split on newlines when possible"""
        # Create a message with newlines that exceeds max length
        line = "A" * 1000
        text = f"{line}\n{line}\n{line}\n{line}\n{line}"

        chunks = split_long_message(text)

        assert len(chunks) > 1
        # Each chunk should end with the newline character or be the last chunk
        for i, chunk in enumerate(chunks[:-1]):
            assert chunk.endswith("\n") or len(chunk) <= MAX_TELEGRAM_MESSAGE_LENGTH

    def test_long_message_forced_split(self):
        """Test that messages without newlines are split at max length"""
        # Create a message without newlines that exceeds max length
        text = "A" * (MAX_TELEGRAM_MESSAGE_LENGTH * 2 + 100)

        chunks = split_long_message(text)

        assert len(chunks) == 3
        assert len(chunks[0]) == MAX_TELEGRAM_MESSAGE_LENGTH
        assert len(chunks[1]) == MAX_TELEGRAM_MESSAGE_LENGTH
        assert len(chunks[2]) == 100

    def test_custom_max_length(self):
        """Test splitting with custom max_length"""
        text = "A" * 100
        max_length = 30

        chunks = split_long_message(text, max_length)

        assert len(chunks) == 4
        assert all(len(chunk) <= max_length for chunk in chunks)

    def test_exact_max_length(self):
        """Test that a message exactly at max length is not split"""
        text = "A" * MAX_TELEGRAM_MESSAGE_LENGTH

        chunks = split_long_message(text)

        assert len(chunks) == 1
        assert chunks[0] == text
