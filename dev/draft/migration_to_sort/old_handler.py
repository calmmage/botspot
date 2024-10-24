import enum
import re
import textwrap
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict
from typing import TYPE_CHECKING, Optional
from typing import Type, List

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import Message, ErrorEvent
from calmapp import App
from calmlib.utils import get_logger
from dotenv import load_dotenv
from pydantic import SecretStr
from pydantic_settings import BaseSettings
from typing_extensions import deprecated

if TYPE_CHECKING:
    from calmapp.app import App

from bot_lib.migration_bot_base.utils.text_utils import (
    MAX_TELEGRAM_MESSAGE_LENGTH,
    split_long_message,
    escape_md,
)
from bot_lib.utils import tools_dir

logger = get_logger(__name__)


class HandlerDisplayMode(enum.Enum):
    FULL = "full"  # each command is displayed separately
    HELP_MESSAGE = "help_message"
    # help message is displayed in the main help command
    # e.g. /help dev

    HELP_COMMAND = "help_command"  # separate help command e.g. /help_dev
    HIDDEN = "hidden"  # hidden from help command


class HandlerConfig(BaseSettings):
    token: SecretStr = SecretStr("")
    api_id: SecretStr = SecretStr("")
    api_hash: SecretStr = SecretStr("")

    send_long_messages_as_files: bool = True
    test_mode: bool = False
    allowed_users: list = []
    dev_message_timeout: int = 5 * 60  # dev message cleanup after 5 minutes

    parse_mode: Optional[ParseMode] = None
    send_preview_for_long_messages: bool = False

    model_config = {
        "env_prefix": "TELEGRAM_BOT_",
    }


# abstract
# class Handler(OldTelegramBot):  # todo: add abc.ABC back after removing OldTelegramBot
name: str = None
display_mode: HandlerDisplayMode = HandlerDisplayMode.HELP_COMMAND
commands: Dict[str, List[str]] = {}  # dict handler_func_name -> command aliases

_config_class: Type[HandlerConfig] = HandlerConfig

# todo: build this automatically from app?
get_commands = []  # list of tuples (app_func_name, handler_func_name)
set_commands = []  # list of tuples (app_func_name, handler_func_name)


def _load_config(self, **kwargs):
    load_dotenv()
    return self._config_class(**kwargs)


def __init__(self, config: _config_class = None, app_data="./app_data"):
    if config is None:
        config = self._load_config()
    self.config = config
    self._app_data = Path(app_data)
    super().__init__()
    self.bot = None
    self._router = None
    self._build_commands_and_add_to_list()

    # Pyrogram
    self._pyrogram_client = None


@property
def pyrogram_client(self):
    if self._pyrogram_client is None:
        self._pyrogram_client = self._init_pyrogram_client()
    return self._pyrogram_client


def register_extra_handlers(self, router):
    # router.message.register(content_types=["location"])(self.handle_location)
    pass


# abstract method chat_handler - to be implemented by child classes
has_chat_handler = False


# todo: rework into property / detect automatically
async def chat_handler(self, message: Message, app: App, **kwargs):
    raise NotImplementedError("Method chat_handler is not implemented")


has_error_handler = False


async def error_handler(self, event: ErrorEvent, message: Message, **kwargs):
    raise NotImplementedError("Method error_handler is not implemented")


# todo: check if I can pass the bot on startup - automatically by dispatcher?
def on_startup(self, bot: Bot):
    self.bot = bot


@property
@deprecated("Found old (pre-migration) style usage of _aiogram_bot. please rework and replace with self.bot")
def _aiogram_bot(self):
    return self.bot


def _build_commands_and_add_to_list(self):
    for app_func_name, handler_func_name in self.get_commands:
        handler = self._build_simple_get_handler(app_func_name)
        setattr(self, handler_func_name, handler)
        self.commands[handler_func_name] = app_func_name
    for app_func_name, handler_func_name in self.set_commands:
        handler = self._build_simple_set_handler(app_func_name)
        setattr(self, handler_func_name, handler)
        self.commands[handler_func_name] = app_func_name


def _build_simple_set_handler(self, name: str):
    async def handler(message: Message, app: App):
        text = self.strip_command(message.text)
        user = self.get_user(message)
        func = getattr(app, name)
        result = func(text, user)
        await message.answer(result)

    return handler


def _build_simple_get_handler(self, name: str):
    async def handler(message: Message, app: App):
        user = self.get_user(message)
        func = getattr(app, name)
        result = func(user)
        await message.answer(result)

    return handler


@staticmethod
def strip_command(text: str):
    if text.startswith("/"):
        parts = text.split(" ", 1)
        if len(parts) > 1:
            return parts[1].strip()
        return ""
    return text


def _get_short_description(self, name):
    desc = getattr(self, name).__doc__
    if desc is None or desc.strip() == "":
        return "No description provided"
    return desc.splitlines()[0]


async def nested_help_handler(self, message: Message):
    # return list of commands
    help_message = "Available commands:\n"
    for command, aliases in self.commands.items():
        if isinstance(aliases, str):
            aliases = [aliases]
        for alias in aliases:
            help_message += f"/{alias}\n"
            help_message += f"  {self._get_short_description(command)}\n"
    await message.reply(help_message)


# region text -> command args - Command Input Magic Parsing
def _parse_message_text(self, message_text: str) -> dict:
    result = {}
    # drop the /command part if present
    message_text = self.strip_command(message_text)

    # if it's not code - parse hashtags
    if "#code" in message_text:
        hashtags, message_text = message_text.split("#code", 1)
        # result.update(self._parse_attributes(hashtags))
        if message_text.strip():
            result["description"] = message_text
    elif "```" in message_text:
        hashtags, _ = message_text.split("```", 1)
        result.update(self._parse_attributes(hashtags))
        result["description"] = message_text
    else:
        result.update(self._parse_attributes(message_text))
        result["description"] = message_text
    return result


hashtag_re = re.compile(r"#\w+")
attribute_re = re.compile(r"(\w+)=(\w+)")
# todo: make abstract
# todo: add docstring / help string/ a way to view this list of
#  recognized tags. Log when a tag is recognized
# recognized_hashtags = {  # todo: add tags or type to preserve info
#     '#idea': {'queue': 'ideas'},
#     '#task': {'queue': 'tasks'},
#     '#shopping': {'queue': 'shopping'},
#     '#recommendation': {'queue': 'recommendations'},
#     '#feed': {'queue': 'feed'},
#     '#content': {'queue': 'content'},
#     '#feedback': {'queue': 'feedback'}
# }
# todo: how do I add a docstring / example of the proper format?
recognized_hashtags: Dict[str, Dict[str, str]] = {}


def _parse_attributes(self, text):
    result = {}
    # use regex to extract hashtags
    # parse hashtags
    hashtags = self.hashtag_re.findall(text)
    # if hashtag is recognized - parse it
    for hashtag in hashtags:
        if hashtag in self.recognized_hashtags:
            self.logger.debug(f"Recognized hashtag: {hashtag}")
            # todo: support combining multiple queues / tags
            #  e.g. #idea #task -> queues = [ideas, tasks]
            result.update(self.recognized_hashtags[hashtag])
        else:
            self.logger.debug(f"Custom hashtag: {hashtag}")
            result[hashtag[1:]] = True

    # parse explicit keys like queue=...
    attributes = self.attribute_re.findall(text)
    for key, value in attributes:
        self.logger.debug(f"Recognized attribute: {key}={value}")
        result[key] = value

    return result


# endregion

# region send_safe - solve issues with long messages and markdown

PREVIEW_CUTOFF = 500


@staticmethod
def _check_is_message(item):
    return isinstance(item, Message)


@staticmethod
def _check_is_chat_id(item):
    return isinstance(item, int) or (isinstance(item, str) and item and item[1:].isdigit())


@staticmethod
def _check_is_text(item):
    return isinstance(item, str)


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


async def func_handler(self, func, message, async_func=False):
    """
    A wrapper to convert an application function into a telegram handler
    Extract the text from the message and pass it to the function
    Run the function and send the result as a message
    """
    # todo: extract kwargs from the message
    # i think I did this code multiple times already.. - find!
    message_text = await self.get_message_text(message)
    # parse text into kwargs
    message_text = self.strip_command(message_text)
    result = self._parse_message_text(message_text)
    if async_func:
        response_text = await func(**result)
    else:
        response_text = func(**result)
    await self.answer_safe(message, response_text)


# endregion

# region file ops


async def download_file(self, message: Message, file_desc, file_path=None):
    if file_desc.file_size < 20 * 1024 * 1024:
        return await self.bot.download(file_desc.file_id, destination=file_path)
    else:
        return await self.download_large_file(message.chat.username, message.message_id, target_path=file_path)


def _check_pyrogram_tokens(self):
    # todo: update, rework self.config, make it per-user
    if not (self.config.api_id.get_secret_value() and self.config.api_hash.get_secret_value()):
        raise ValueError("Telegram api_id and api_hash must be provided for Pyrogram " "to download large files")


def _init_pyrogram_client(self):
    import pyrogram

    return pyrogram.Client(
        self.__class__.__name__,
        api_id=self.config.api_id.get_secret_value(),
        api_hash=self.config.api_hash.get_secret_value(),
        bot_token=self.config.token.get_secret_value(),
    )


@property
def tools_dir(self):
    return tools_dir


@property
def download_large_file_script_path(self):
    return self.tools_dir / "download_file_with_pyrogram.py"


@property
def app_data(self):
    if not self._app_data.exists():
        self._app_data.mkdir(parents=True, exist_ok=True)
    return self._app_data


@property
def downloads_dir(self):
    if not self.app_data.exists():
        self.app_data.mkdir(parents=True, exist_ok=True)
    return self.app_data / "downloads"


# endregion file ops
