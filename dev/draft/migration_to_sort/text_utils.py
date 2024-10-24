import re

MAX_TELEGRAM_MESSAGE_LENGTH = 4096


def split_long_message(text, max_length=MAX_TELEGRAM_MESSAGE_LENGTH, sep="\n"):
    chunks = []
    while len(text) > max_length:
        chunk = text[:max_length]
        if sep:
            # split the text on the last sep character, if it exists
            last_sep = chunk.rfind(sep)
            if last_sep != -1:
                chunk = chunk[: last_sep + 1]
        text = text[len(chunk) :]
        chunks.append(chunk)
    if text:
        chunks.append(text)  # add the remaining text as the last chunk
    return chunks


SPECIAL_CHARS = r"\\_\*\[\]\(\)~`><&#+\-=\|\{\}\.\!"

escape_re = re.compile(f"[{SPECIAL_CHARS}]")


def escape_md(text: str) -> str:
    """Escape markdown special characters in the text."""
    return escape_re.sub(r"\\\g<0>", text)
