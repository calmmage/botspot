import re
from typing import List

# Constants
MAX_TELEGRAM_MESSAGE_LENGTH = 4096


def escape_md(text: str) -> str:
    """
    Escape Markdown special characters in text.

    Args:
        text: Text to escape

    Returns:
        Escaped text safe for Markdown parsing
    """
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", str(text))


def split_long_message(
    text: str, max_length: int = MAX_TELEGRAM_MESSAGE_LENGTH
) -> List[str]:
    """
    Split long message into chunks that fit Telegram's message length limit.
    Tries to split on newlines when possible.

    Args:
        text: Text to split
        max_length: Maximum length of each chunk

    Returns:
        List of message chunks
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break

        # Try to split on newline first
        split_pos = text.rfind("\n", 0, max_length)

        # If no newline found, split at maximum length
        if split_pos == -1:
            split_pos = max_length

        chunks.append(text[:split_pos])
        text = text[split_pos:].lstrip()

    return chunks
