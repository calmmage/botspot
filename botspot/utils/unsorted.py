from typing import Dict, Union

from aiogram.types import Message
from loguru import logger


def get_user(message: Message, forward_priority=False) -> str:
    if forward_priority and hasattr(message, "forward_from") and message.forward_from:
        user = message.forward_from
    else:
        user = message.from_user
    return user.username or user.id


def get_name(message: Message, forward_priority=False) -> str:
    if forward_priority and hasattr(message, "forward_from") and message.forward_from:
        user = message.forward_from
    else:
        user = message.from_user
    return user.full_name


async def get_message_text(message: Message, as_markdown=False, include_reply=False) -> str:
    """
    Extract text from the message - including text, caption, voice messages, and text files
    :param message: aiogram Message object
    :param as_markdown: extract text with markdown formatting
    :param include_reply: include text from the message this message is replying to
    :return: extracted text concatenated from all sources
    """
    result = await _extract_message_text(message, as_markdown, include_reply, as_dict=True)
    # todo: if context_builder component enabled - augment with context from middleware
    return "\n\n".join(result.values())


async def _extract_message_text(
    message: Message,
    as_markdown=False,
    include_reply=False,
    as_dict=False,  # todo: change default to True
) -> Union[Dict, str]:
    result = {}
    # option 1: message text
    if message.text:
        if as_markdown:
            result["text"] = message.md_text
        else:
            result["text"] = message.text
    # option 2: caption
    if message.caption:
        if as_markdown:
            logger.warning("Markdown captions are not supported yet")
        result["caption"] = message.caption

    # option 3: voice/video message
    # if message.voice or message.audio:
    #     # todo: accept voice message? Seems to work
    #     chunks = await _process_voice_message(message)
    #     result["audio"] = "\n\n".join(chunks)
    # todo: accept files?
    if message.document and message.document.mime_type == "text/plain":
        from botspot.core.dependency_manager import get_dependency_manager

        deps = get_dependency_manager()
        logger.info(f"Received text file: {message.document.file_name}")
        file = await deps.bot.download(message.document.file_id)
        content = file.read().decode("utf-8")
        result["document"] = f"\n\n{content}"
    # todo: accept video messages?
    # if message.document:

    # todo: extract text from Replies? No, do that explicitly
    if include_reply and hasattr(message, "reply_to_message") and message.reply_to_message:
        reply_text = await _extract_message_text(
            message.reply_to_message,
            as_markdown=as_markdown,
            include_reply=False,
            as_dict=False,
        )
        result["reply_to"] = f"\n\n{reply_text}"

    # option 4: content - only extract if explicitly asked?
    # support multi-message content extraction?
    # todo: ... if content_parsing_mode is enabled - parse content text
    if as_dict:
        return result
    return "\n\n".join(result.values())


def strip_command(text: str):
    if text.startswith("/"):
        parts = text.split(" ", 1)
        if len(parts) > 1:
            return parts[1].strip()
        return ""
    return text
