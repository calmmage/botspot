import textwrap
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Union

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import BufferedInputFile, Message
from loguru import logger

from botspot.utils.text_utils import MAX_TELEGRAM_MESSAGE_LENGTH, escape_md, split_long_message

if TYPE_CHECKING:
    from botspot.core.dependency_manager import DependencyManager

from pydantic_settings import BaseSettings


class SendSafeSettings(BaseSettings):
    """Settings for send_safe utility"""

    # Feature flags
    enabled: bool = True
    wrap_text: bool = False
    send_long_messages_as_files: bool = True
    send_preview_for_long_messages: bool = False

    # Configuration
    preview_cutoff: int = 200
    wrap_width: int = 88
    parse_mode: ParseMode = ParseMode.HTML  # or "MarkdownV2", "Markdown", None

    class Config:
        env_prefix = "BOTSPOT_SEND_SAFE_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


async def _send_with_parse_mode_fallback(
    bot: Bot,
    chat_id: Union[int, str],
    text: str,
    parse_mode: Optional[str] = None,
    **kwargs,
) -> Message:
    """
    Send message with parse mode fallback to plain text if formatting fails.

    Args:
        bot: Bot instance
        chat_id: Chat ID
        text: Text to send
        parse_mode: Parse mode to use (if None, uses bot's default)
        **kwargs: Additional arguments for send_message

    Returns:
        Sent message
    """
    try:
        if parse_mode is None:
            # if parse_mode is None, send message without parse mode - uses default parse mode of the bot
            return await bot.send_message(chat_id, text, **kwargs)
        else:
            # if parse_mode is specified, send message with specified parse mode
            return await bot.send_message(chat_id, text, parse_mode=parse_mode, **kwargs)
    except Exception:
        # Fallback to plain text if formatting fails
        logger.warning(f"Failed to send message {text} with parse mode, falling back to plain text")
        return await bot.send_message(chat_id, text, parse_mode=None, **kwargs)


async def send_safe(
    chat_id: Union[int, str, Message],
    text: str,
    deps: Optional["DependencyManager"] = None,
    reply_to_message_id: Optional[int] = None,
    filename: Optional[str] = None,
    escape_markdown: bool = False,
    wrap: Optional[bool] = None,
    parse_mode: Optional[str] = None,
    **kwargs,
):
    """
    Send message with safe mode and various formatting options

    Args:
        chat_id: Chat ID or Message object
        text: Text to send
        deps: DependencyManager instance
        reply_to_message_id: Message to reply to
        filename: Optional filename when sending as file
        escape_markdown: Whether to escape markdown characters
        wrap: Whether to wrap text (overrides settings)
        parse_mode: Message parse mode (overrides settings)
        **kwargs: Additional arguments for send_message
    """
    if deps is None:
        from botspot.core.dependency_manager import get_dependency_manager

        deps = get_dependency_manager()

    bot = deps.bot
    settings = deps.botspot_settings.send_safe

    # Handle Message object input
    if isinstance(chat_id, Message):
        message = chat_id
        chat_id = message.chat.id
        reply_to_message_id = message.message_id

    # Ensure chat_id is int
    if isinstance(chat_id, str):
        chat_id = int(chat_id)

    if not settings.enabled:
        return await bot.send_message(
            chat_id, text, reply_to_message_id=reply_to_message_id, **kwargs
        )

    # Text wrapping (use parameter if provided, otherwise use settings)
    should_wrap = wrap if wrap is not None else settings.wrap_text
    if should_wrap:
        lines = text.split("\n")
        new_lines = [textwrap.fill(line, width=settings.wrap_width) for line in lines]
        text = "\n".join(new_lines)

    # Escape markdown if needed
    if escape_markdown:
        text = escape_md(text)

    # Handle long messages
    if settings.send_long_messages_as_files and len(text) > MAX_TELEGRAM_MESSAGE_LENGTH:
        if filename is None:
            filename = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"

        # Send preview if configured
        if settings.send_preview_for_long_messages:
            preview = text[: settings.preview_cutoff]
            preview_text = (
                f"Message is too long, sending as file {filename}\nPreview:\n{preview}..."
            )
            await _send_with_parse_mode_fallback(
                bot,
                chat_id,
                preview_text,
                parse_mode=parse_mode or settings.parse_mode,
                **kwargs,
            )

        # Send as file
        file = BufferedInputFile(text.encode("utf-8"), filename)
        return await bot.send_document(
            chat_id, file, reply_to_message_id=reply_to_message_id, **kwargs
        )

    # Split long messages if not sending as files
    if len(text) > MAX_TELEGRAM_MESSAGE_LENGTH:
        messages = []
        for chunk in split_long_message(text):
            msg = await _send_with_parse_mode_fallback(
                bot,
                chat_id,
                chunk,
                parse_mode=parse_mode or settings.parse_mode,
                reply_to_message_id=reply_to_message_id,
                **kwargs,
            )
            messages.append(msg)
        return messages[-1]  # Return the last message

    # Send as regular message
    return await _send_with_parse_mode_fallback(
        bot,
        chat_id,
        text,
        parse_mode=parse_mode or settings.parse_mode,
        reply_to_message_id=reply_to_message_id,
        **kwargs,
    )


async def reply_safe(message: Message, text: str, **kwargs):
    """Reply to a message with safe sending"""
    await send_safe(message.chat.id, text, reply_to_message_id=message.message_id, **kwargs)


async def answer_safe(message: Message, text: str, **kwargs):
    """Answer to a message with safe sending"""
    await send_safe(message.chat.id, text, **kwargs)


if __name__ == "__main__":
    import asyncio

    from aiogram.types import Message

    async def message_handler(message: Message):
        super_long_text = "This is a very long message. " * 100
        await send_safe(message.chat.id, super_long_text)

    asyncio.run(message_handler(Message(chat={"id": 123456789})))
