import textwrap
import traceback
from datetime import datetime
from typing import Optional

from aiogram.types import Message

from dev.draft.migration_to_sort.text_utils import escape_md, MAX_TELEGRAM_MESSAGE_LENGTH, split_long_message


async def send_safe(
    self,
    chat_id: int,
    text: str,
    reply_to_message_id: Optional[int] = None,
    filename=None,
    escape_markdown=False,
    wrap=True,
    parse_mode=None,
    **kwargs,  # todo: add everywhere below to send
):
    # backward compat: check if chat_id and text are swapped
    if self._check_is_chat_id(text) and self._check_is_text(chat_id):
        # warning
        self.logger.warning(
            "chat_id and text are swapped. "
            "Please use send_safe(text, chat_id) instead. "
            "Old usage is deprecated and will be removed in next version"
        )
        chat_id, text = text, chat_id

    if self._check_is_message(chat_id):
        self.logger.warning(
            "message instance is passed instead of chat_id "
            "Please use send_safe(text, chat_id, reply_to_message_id=) instead. "
            "Old usage is deprecated and will be removed in next version"
        )
        # noinspection PyTypeChecker
        message: Message = chat_id
        chat_id = message.chat.id
        reply_to_message_id = message.message_id
    if isinstance(chat_id, str):
        chat_id = int(chat_id)

    if wrap:
        lines = text.split("\n")
        new_lines = [textwrap.fill(line, width=88) for line in lines]
        text = "\n".join(new_lines)
    # todo: add 3 send modes - always text, always file, auto
    if self.send_long_messages_as_files:
        if len(text) > MAX_TELEGRAM_MESSAGE_LENGTH:
            if filename is None:
                filename = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
            if self.config.send_preview_for_long_messages:
                preview = text[: self.PREVIEW_CUTOFF]
                if escape_markdown:
                    preview = escape_md(preview)
                await self.bot.send_message(
                    chat_id,
                    textwrap.dedent(
                        f"""
                        Message is too long, sending as file {escape_md(filename)} 
                        Preview: 
                        """
                    )
                    + preview
                    + "...",
                    **kwargs,
                )

            return await self._send_as_file(
                chat_id,
                text,
                reply_to_message_id=reply_to_message_id,
                filename=filename,
                **kwargs,
            )
        else:  # len(text) < MAX_TELEGRAM_MESSAGE_LENGTH:
            message_text = text
            if escape_markdown:
                message_text = escape_md(text)
            if filename:
                message_text = escape_md(filename) + "\n" + message_text
            return await self._send_with_parse_mode_fallback(
                text=message_text,
                chat_id=chat_id,
                reply_to_message_id=reply_to_message_id,
                parse_mode=parse_mode,
                **kwargs,
            )
    else:  # not self.send_long_messages_as_files
        for chunk in split_long_message(text):
            if escape_markdown:
                chunk = escape_md(chunk)
            return await self._send_with_parse_mode_fallback(
                chat_id,
                chunk,
                reply_to_message_id=reply_to_message_id,
                parse_mode=parse_mode,
                **kwargs,
            )


async def _send_with_parse_mode_fallback(self, chat_id, text, reply_to_message_id=None, parse_mode=None, **kwargs):
    """
    Send message with parse_mode=None if parse_mode is not supported
    """
    if parse_mode is None:
        parse_mode = self.config.parse_mode
    try:
        return await self.bot.send_message(
            chat_id,
            text,
            reply_to_message_id=reply_to_message_id,
            parse_mode=parse_mode,
            **kwargs,
        )
    except Exception:
        self.logger.warning(
            f"Failed to send message with parse_mode={parse_mode}. "
            f"Retrying with parse_mode=None"
            f"Exception: {traceback.format_exc()}"
            # todo , data=traceback.format_exc()
        )
        return await self.bot.send_message(
            chat_id,
            text,
            reply_to_message_id=reply_to_message_id,
            parse_mode=None,
            **kwargs,
        )


@property
def send_long_messages_as_files(self):
    return self.config.send_long_messages_as_files


async def _send_as_file(self, chat_id, text, reply_to_message_id=None, filename=None, **kwargs):
    """
    Send text as a file to the chat
    :param chat_id:
    :param text:
    :param reply_to_message_id:
    :param filename:
    :return:
    """
    from aiogram.types.input_file import BufferedInputFile

    temp_file = BufferedInputFile(text.encode("utf-8"), filename)
    await self.bot.send_document(chat_id, temp_file, reply_to_message_id=reply_to_message_id, **kwargs)


# endregion


# region utils - move to the base class
async def reply_safe(self, message: Message, response_text: str, **kwargs):
    """
    Respond to a message with a given text
    If the response text is too long, split it into multiple messages
    """
    if isinstance(message, str):
        message, response_text = response_text, message
    """
    Respond to a message with a given text
    If the response text is too long, split it into multiple messages
    """
    chat_id = message.chat.id
    return await self.send_safe(chat_id, response_text, reply_to_message_id=message.message_id, **kwargs)


async def answer_safe(self, message: Message, response_text: str, **kwargs):
    """
    Respond to a message with a given text
    If the response text is too long, split it into multiple messages
    """
    if isinstance(message, str):
        message, response_text = response_text, message
    """
    Answer to a message with a given text
    If the response text is too long, split it into multiple messages
    """
    chat_id = message.chat.id
    return await self.send_safe(chat_id, response_text, **kwargs)
