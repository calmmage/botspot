from io import BytesIO
from typing import BinaryIO, Dict, List, Optional, Union

from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext
from aiogram.types import Audio, Document, Message, PhotoSize, Video, VideoNote, Voice
from botspot.utils.user_ops import UserLike
from loguru import logger


def get_user(message: Message, forward_priority=False) -> str:
    if forward_priority and hasattr(message, "forward_from") and message.forward_from:
        user = message.forward_from
    else:
        user = message.from_user
    # todo: use User Record instead?
    assert user is not None
    return user.username or str(user.id)


def get_name(message: Message, forward_priority=False) -> str:
    if forward_priority and hasattr(message, "forward_from") and message.forward_from:
        user = message.forward_from
    else:
        user = message.from_user
    return user.full_name


async def send_typing_status(message: Message, action: str = "typing"):
    """
    Send typing or other chat action status to the chat.

    Args:
        message: The message object to get chat_id from
        action: Chat action to send, default is "typing"
               Other options include: "upload_photo", "record_video", "upload_video",
               "record_voice", "upload_voice", "upload_document", "choose_sticker",
               "find_location", "record_video_note", "upload_video_note"

    Usage:
        await send_typing_status(message)
        await send_typing_status(message, "upload_document")
    """
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    chat_action = action

    # Convert string to ChatAction enum if needed
    if isinstance(action, str):
        try:
            chat_action = ChatAction(action)
        except ValueError:
            logger.warning(f"Invalid chat action: {action}, using 'typing' instead")
            chat_action = ChatAction.TYPING

    await deps.bot.send_chat_action(chat_id=message.chat.id, action=chat_action)


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


Attachment = Union[PhotoSize, Document, Video, Audio, Voice, VideoNote]


# for getting attachment format for llm query attachment
def get_attachment_format(attachment: Attachment) -> str:
    if isinstance(attachment, PhotoSize):
        return "image/jpeg"
    elif isinstance(attachment, Document):
        # todo: make sure file name is provided here
        assert attachment.file_name is not None
        stem = attachment.file_name.split(".")[-1]

        format = f"application/{stem}"  # "application/pdf"
        # todo: check if mime type is always provided - then use it instead
        if not format == attachment.mime_type:
            logger.warning(
                f"File {attachment.file_name} has mime type {attachment.mime_type}, expected {format}"
            )
        return format
    else:
        raise ValueError(f"Unknown attachment type: {type(attachment)}")


def get_message_attachments(message: Message) -> List[Attachment]:
    attachments = []
    if message.photo:
        attachments.append(message.photo[-1])
    if message.document:
        attachments.append(message.document)
    if message.video:
        attachments.append(message.video)
    if message.audio:
        attachments.append(message.audio)
    if message.voice:
        attachments.append(message.voice)
    if hasattr(message, "video_note") and message.video_note:
        attachments.append(message.video_note)
    # Optionally add more types for completeness
    # if hasattr(message, 'animation') and message.animation:
    #     attachments.append(message.animation)
    # if hasattr(message, 'sticker') and message.sticker:
    #     attachments.append(message.sticker)
    # if hasattr(message, 'contact') and message.contact:
    #     attachments.append(message.contact)
    # if hasattr(message, 'location') and message.location:
    #     attachments.append(message.location)
    return attachments


def is_telegram_attachment(attachment: Attachment) -> bool:
    return not isinstance(attachment, BinaryIO)


async def download_telegram_file(
    attachment: Attachment,
    message: Optional[Message] = None,
    user: Optional[UserLike] = None,
    state: Optional[FSMContext] = None,
) -> BinaryIO:
    try:
        return await _download_telegram_file_aiogram(attachment)
    except Exception as e:
        logger.error(
            f"Failed to download file {getattr(attachment, 'file_id', None)} with aiogram, trying telethon: {e}"
        )
        return await _download_telegram_file_telethon(
            attachment, message=message, user=user, state=state
        )


async def _download_telegram_file_aiogram(attachment: Attachment) -> BinaryIO:
    from botspot.utils.deps_getters import get_bot

    file_id = attachment.file_id
    bot = get_bot()

    # Download the file
    file = await bot.get_file(file_id)
    if not file or not file.file_path:
        # return None, None
        # return
        raise ValueError("File not found")

    file_bytes = await bot.download_file(file.file_path)
    if not file_bytes:
        raise ValueError("File not found")
    assert isinstance(file_bytes, (BinaryIO, BytesIO))  # BinaryIO for documents?

    # logger.debug(f"Downloading telegram file with aiogram. Resulting file name: {file_bytes}")

    return file_bytes


async def _download_telegram_file_telethon(
    attachment: Attachment,
    message: Message,
    user: Optional[UserLike] = None,
    state: Optional[FSMContext] = None,
):  #  chat_id=None, message_id=None) -> BinaryIO:
    from botspot.utils.deps_getters import get_telethon_client

    if user is not None:
        from botspot import to_user_record

        user_id = to_user_record(user).user_id
    else:
        user_id = None

    client = await get_telethon_client(user_id=user_id, state=state)

    chat_id = message.chat.id
    message_id = message.message_id

    logger.info(
        f"Trying to download with telethon: chat_id={chat_id}, message_id={message_id}, attachment={attachment}"
    )

    # Try to fetch the message from Telethon
    telethon_message = await client.get_messages(chat_id, ids=message_id)
    if telethon_message is None:
        raise ValueError("Could not resolve message for telethon download.")

    file_data = await client.download_media(message, file=BytesIO())
    if isinstance(file_data, BytesIO):
        file_data.seek(0)
        logger.info(
            f"Downloaded file to BytesIO using telethon, size={file_data.getbuffer().nbytes}"
        )
        return file_data
    elif isinstance(file_data, str):
        with open(file_data, "rb") as f:
            data = BytesIO(f.read())
        logger.info(
            f"Downloaded file to disk using telethon, loaded to BytesIO, size={data.getbuffer().nbytes}"
        )
        return data
    else:
        raise RuntimeError(f"Telethon download_media returned unexpected type: {type(file_data)}")



async def get_username_from_message(
        chat_id: int,
        state: FSMContext,
        prompt: str = "Please send the username or forward a message from that user:",
        cleanup: bool = False,
        timeout: Optional[int] = None,
        max_retries: int = 3,
) -> Optional[str]:
    """
    Get username from user with multiple input methods.

    Supports:
    1. Text message with @username, username, or user ID
    2. Forwarded message (extracts from forward_from)
    3. Retry logic for invalid inputs

    Args:
        chat_id: Chat ID to send prompt to
        state: FSM context for state management
        prompt: Prompt message to show user
        cleanup: Whether to cleanup messages after interaction
        timeout: Timeout in seconds (None for no timeout)
        max_retries: Maximum number of retry attempts

    Returns:
        Username (with @ prefix for usernames, plain for user IDs) or None if failed

    Examples:
        >>> username = await get_username_from_message(chat_id, state)
        >>> # User can:
        >>> # 1. Send: "@john" or "john" or "123456789"
        >>> # 2. Forward a message from john
        >>> # Result: "@john" or "123456789"
    """
    for attempt in range(max_retries):
        from botspot.components.features.user_interactions import ask_user_raw
        # Ask user for username or forward
        logger.info(
            f"Asking for username (attempt {attempt + 1}/{max_retries})..."
        )
        response_message: Optional[Message] = await ask_user_raw(
            chat_id=chat_id,
            question=prompt,
            state=state,
            cleanup=cleanup,
            timeout=timeout,
        )

        if response_message is None:
            logger.warning("No response received from user")
            return None

        # Try to extract username from response
        username = _extract_username_from_message(response_message)

        if username:
            logger.info(f"Successfully extracted username: {username}")
            return username

        # Failed to extract, retry with more specific prompt
        if attempt < max_retries - 1:
            prompt = (
                "❌ Could not extract username. Please try again:\n"
                "- Send username: @john or john\n"
                "- Send user ID: 123456789\n"
                "- Forward a message from that user"
            )
        else:
            logger.warning(
                f"Failed to extract username after {max_retries} attempts"
            )
            return None

    return None


def _extract_username_from_message(message: Message) -> Optional[str]:
    """
    Extract username from a message.

    Supports:
    1. Forwarded message -> extract from forward_from
    2. Text message -> parse @username, username, or user ID

    Args:
        message: Message to extract username from

    Returns:
        Username with @ prefix (for usernames) or plain (for user IDs), or None if failed
    """
    # Method 1: Extract from forwarded message
    if message.forward_from:
        # Message forwarded from a user
        user = message.forward_from

        if user.username:
            username = f"@{user.username}"
            logger.info(
                f"Extracted username from forwarded message: {username}"
            )
            return username
        elif user.id:
            # No username, use user ID
            user_id = str(user.id)
            logger.info(
                f"Extracted user ID from forwarded message: {user_id}"
            )
            return user_id
        else:
            logger.warning(
                "Forwarded message from user without username or ID"
            )
            return None

    # Method 2: Extract from text message
    if message.text:
        text = message.text.strip()

        # Check if it's a valid username or user ID
        if text.startswith("@"):
            # Username with @ prefix
            username = text
            logger.info(f"Extracted username from text: {username}")
            return username
        elif text.isdigit():
            # User ID
            user_id = text
            logger.info(f"Extracted user ID from text: {user_id}")
            return user_id
        else:
            # Username without @ prefix
            username = f"@{text}"
            logger.info(
                f"Extracted username from text (added @ prefix): {username}"
            )
            return username

    logger.warning("Could not extract username from message")
    return None


async def get_username_from_command_or_dialog(
        message: Message,
        state: FSMContext,
        cleanup: bool = False,
        prompt: str = "Please send the username or forward a message from that user:",
        timeout: Optional[int] = None,
) -> Optional[str]:
    """
    Get username either from command arguments or via interactive dialog.

    First tries to extract from command text (e.g., /add_friend @john),
    if not found, asks user interactively.

    Args:
        message: Original command message
        state: FSM context
        cleanup: Whether to cleanup messages
        prompt: Prompt for interactive dialog
        timeout: Timeout for interactive dialog

    Returns:
        Username or None if failed
    """
    # Try to get from command arguments first
    if message.text:
        parts = message.text.split(maxsplit=1)
        if len(parts) >= 2:
            # Username provided in command
            username_text = parts[1].strip()

            # Normalize
            if username_text.startswith("@"):
                return username_text
            elif username_text.isdigit():
                return username_text
            else:
                return f"@{username_text}"

    # No username in command, ask interactively
    logger.info("No username in command, asking user interactively")
    return await get_username_from_message(
        chat_id=message.chat.id,
        state=state,
        prompt=prompt,
        cleanup=cleanup,
        timeout=timeout,
    )

