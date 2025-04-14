import asyncio
import textwrap
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Union, Any

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import BufferedInputFile, Chat, Message, User
from botspot.utils.text_utils import (
    MAX_TELEGRAM_MESSAGE_LENGTH,
    escape_md,
    split_long_message,
)
from loguru import logger

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
    auto_delete_enabled: Optional[bool] = (
        None  # None means it will be set based on auto_archive settings
    )
    auto_delete_timeout: int = 10  # seconds

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
            return await bot.send_message(
                chat_id, text, parse_mode=parse_mode, **kwargs
            )
    except Exception:
        # Fallback to plain text if formatting fails
        logger.warning(
            f"Failed to send message {text} with parse mode, falling back to plain text"
        )
        return await bot.send_message(chat_id, text, parse_mode=None, **kwargs)


async def _handle_message_input(
    chat_id: Union[int, str, Message],
) -> tuple[int, Optional[int]]:
    """Handle Message object input and convert chat_id to int.

    Args:
        chat_id: Chat ID or Message object

    Returns:
        Tuple of (chat_id, reply_to_message_id)
    """
    reply_to_message_id = None

    if isinstance(chat_id, Message):
        message = chat_id
        chat_id = message.chat.id
        reply_to_message_id = message.message_id

    # Ensure chat_id is int
    if isinstance(chat_id, str):
        chat_id = int(chat_id)

    return chat_id, reply_to_message_id


async def _prepare_text(
    text: str,
    settings: SendSafeSettings,
    wrap: Optional[bool] = None,
    escape_markdown: bool = False,
) -> str:
    """Prepare text for sending by applying wrapping and markdown escaping.

    Args:
        text: Original text
        settings: SendSafeSettings instance
        wrap: Whether to wrap text (overrides settings)
        escape_markdown: Whether to escape markdown characters

    Returns:
        Prepared text
    """
    # Text wrapping (use parameter if provided, otherwise use settings)
    should_wrap = wrap if wrap is not None else settings.wrap_text
    if should_wrap:
        lines = text.split("\n")
        new_lines = [textwrap.fill(line, width=settings.wrap_width) for line in lines]
        text = "\n".join(new_lines)

    # Escape markdown if needed
    if escape_markdown:
        text = escape_md(text)

    return text


async def _send_long_message_as_file(
    bot: Bot,
    chat_id: int,
    text: str,
    settings: SendSafeSettings,
    reply_to_message_id: Optional[int] = None,
    filename: Optional[str] = None,
    parse_mode: Optional[str] = None,
    **kwargs,
) -> Message:
    """Send a long message as a file with optional preview.

    Args:
        bot: Bot instance
        chat_id: Chat ID
        text: Text to send
        settings: SendSafeSettings instance
        reply_to_message_id: Message to reply to
        filename: Optional filename
        parse_mode: Message parse mode
        **kwargs: Additional arguments for send_message

    Returns:
        Sent message
    """
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


async def _send_split_messages(
    bot: Bot,
    chat_id: int,
    text: str,
    settings: SendSafeSettings,
    reply_to_message_id: Optional[int] = None,
    parse_mode: Optional[str] = None,
    **kwargs,
) -> Message:
    """Send a long message split into multiple parts.

    Args:
        bot: Bot instance
        chat_id: Chat ID
        text: Text to send
        settings: SendSafeSettings instance
        reply_to_message_id: Message to reply to
        parse_mode: Message parse mode
        **kwargs: Additional arguments for send_message

    Returns:
        Last sent message
    """
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
    return messages[-1]


async def _handle_auto_delete(
    sent_message: Message,
    settings: SendSafeSettings,
    deps: "DependencyManager",
    cleanup: Optional[bool] = None,
    cleanup_timeout: Optional[int] = None,
) -> None:
    """Handle auto-deletion and forwarding to auto_archive.

    Args:
        sent_message: The message that was sent
        settings: SendSafeSettings instance
        deps: DependencyManager instance
        cleanup: Whether to enable auto-deletion (overrides settings)
        cleanup_timeout: Timeout in seconds for auto-deletion (overrides settings)
    """
    # Determine if auto-deletion should be enabled
    should_delete = cleanup if cleanup is not None else settings.auto_delete_enabled
    if not should_delete:
        return

    # Forward to auto_archive if enabled and bound
    if (
        deps.botspot_settings.auto_archive.enabled
        and deps.botspot_settings.auto_archive.forward_sent_messages
    ):
        from botspot.components.new.chat_binder import get_bound_chat
        from botspot.core.errors import ChatBindingNotFoundError

        try:
            if sent_message.from_user and sent_message.from_user.id:
                target_chat_id = await get_bound_chat(
                    sent_message.chat.id,
                    key=deps.auto_archive.settings.chat_binding_key,
                )
                await sent_message.forward(target_chat_id)
        except ChatBindingNotFoundError:
            # no binding found, do nothing
            pass

    # Schedule auto-deletion
    async def delete_message():
        timeout = (
            cleanup_timeout
            if cleanup_timeout is not None
            else settings.auto_delete_timeout
        )
        await asyncio.sleep(timeout)
        try:
            await sent_message.delete()
        except Exception as e:
            logger.warning(f"Failed to auto-delete message: {e}")

    asyncio.create_task(delete_message())


async def send_safe(
    chat_id: Union[int, str, Message],
    text: str,
    deps: Optional["DependencyManager"] = None,
    reply_to_message_id: Optional[int] = None,
    filename: Optional[str] = None,
    escape_markdown: bool = False,
    wrap: Optional[bool] = None,
    parse_mode: Optional[str] = None,
    cleanup: Optional[bool] = None,
    cleanup_timeout: Optional[int] = None,
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
        cleanup: Whether to enable auto-deletion (overrides settings)
        cleanup_timeout: Timeout in seconds for auto-deletion (overrides settings)
        **kwargs: Additional arguments for send_message
    """
    if deps is None:
        from botspot.core.dependency_manager import get_dependency_manager

        deps = get_dependency_manager()

    bot = deps.bot
    settings = deps.botspot_settings.send_safe

    # Handle Message object input and convert chat_id
    chat_id, input_reply_id = await _handle_message_input(chat_id)
    reply_to_message_id = reply_to_message_id or input_reply_id

    if not settings.enabled:
        return await bot.send_message(
            chat_id, text, reply_to_message_id=reply_to_message_id, **kwargs
        )

    # Prepare text
    text = await _prepare_text(text, settings, wrap, escape_markdown)

    # Handle long messages
    if settings.send_long_messages_as_files and len(text) > MAX_TELEGRAM_MESSAGE_LENGTH:
        sent_message = await _send_long_message_as_file(
            bot,
            chat_id,
            text,
            settings,
            reply_to_message_id,
            filename,
            parse_mode,
            **kwargs,
        )
    else:
        # Split long messages if not sending as files
        if len(text) > MAX_TELEGRAM_MESSAGE_LENGTH:
            sent_message = await _send_split_messages(
                bot, chat_id, text, settings, reply_to_message_id, parse_mode, **kwargs
            )
        else:
            # Send as regular message
            sent_message = await _send_with_parse_mode_fallback(
                bot,
                chat_id,
                text,
                parse_mode=parse_mode or settings.parse_mode,
                reply_to_message_id=reply_to_message_id,
                **kwargs,
            )

    # Handle auto-deletion
    await _handle_auto_delete(sent_message, settings, deps, cleanup, cleanup_timeout)

    return sent_message


async def reply_safe(
    message: Message,
    text: str,
    *,
    deps: Optional["DependencyManager"] = None,
    filename: Optional[str] = None,
    escape_markdown: bool = False,
    wrap: Optional[bool] = None,
    parse_mode: Optional[str] = None,
    cleanup: Optional[bool] = None,
    cleanup_timeout: Optional[int] = None,
    **kwargs: Any,
) -> Message:
    """Reply to a message with safe sending"""
    return await send_safe(
        message.chat.id,
        text,
        deps=deps,
        reply_to_message_id=message.message_id,
        filename=filename,
        escape_markdown=escape_markdown,
        wrap=wrap,
        parse_mode=parse_mode,
        cleanup=cleanup,
        cleanup_timeout=cleanup_timeout,
        **kwargs,
    )


async def answer_safe(
    message: Message,
    text: str,
    *,
    deps: Optional["DependencyManager"] = None,
    filename: Optional[str] = None,
    escape_markdown: bool = False,
    wrap: Optional[bool] = None,
    parse_mode: Optional[str] = None,
    cleanup: Optional[bool] = None,
    cleanup_timeout: Optional[int] = None,
    **kwargs: Any,
) -> Message:
    """Answer to a message with safe sending"""
    return await send_safe(
        message.chat.id,
        text,
        deps=deps,
        filename=filename,
        escape_markdown=escape_markdown,
        wrap=wrap,
        parse_mode=parse_mode,
        cleanup=cleanup,
        cleanup_timeout=cleanup_timeout,
        **kwargs,
    )


if __name__ == "__main__":

    async def message_handler(message: Message):
        super_long_text = "This is a very long message. " * 100
        await send_safe(message.chat.id, super_long_text)

    asyncio.run(
        message_handler(
            Message(
                chat=Chat(id=123456789, type="private"),
                message_id=1,
                date=datetime.now(),
                from_user=User(id=123456789, is_bot=False, first_name="Test"),
            )
        )
    )
