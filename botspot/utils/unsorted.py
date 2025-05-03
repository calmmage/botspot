from io import BytesIO
from typing import BinaryIO, Dict, List, Union

from aiogram.enums import ChatAction
from aiogram.types import Audio, Document, Message, PhotoSize, Video, Voice
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


Attachment = Union[PhotoSize, Document, Video, Audio, Voice]


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
    # todo: figure out how to get all attachment types
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
    return attachments


def is_telegram_attachment(attachment: Attachment) -> bool:
    return not isinstance(attachment, BinaryIO)


async def download_telegram_file(attachment: Attachment) -> BinaryIO:
    try:
        return await _download_telegram_file_aiogram(attachment)
    except:
        logger.error(f"Failed to download file {attachment.file_id} with aiogram, trying telethon")
        return await _download_telegram_file_telethon(attachment)


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


async def _download_telegram_file_telethon(attachment: Attachment) -> BinaryIO:
    raise NotImplementedError("Telethon downloading is not implemented")
