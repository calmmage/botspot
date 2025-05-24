import asyncio
import json
import random
from abc import abstractmethod
from collections import defaultdict, deque
from datetime import datetime
from functools import wraps
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, List, Optional, Union

import loguru
from aiogram import F, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from pydantic import BaseModel

if TYPE_CHECKING:
    from bot_lib.migration_bot_base.core import App


class CommandRegistryItem(BaseModel):
    commands: List[str]
    handler_name: str
    description: Optional[str]
    filters: list


def admin(func):
    # todo: implement properly
    # @wraps(func)
    # async def wrapped(self, message: types.Message):
    #     if message.from_user.username not in self.config.admins:
    #         self.logger.info(f"Unauthorized user {message.from_user.username}")
    #         await message.answer(self.UNAUTHORISED_RESPONSE)
    #         return
    #     return await func(self, message)
    #
    # return wrapped
    return func


# todo: find and use simple_command decorator that parses the incoming
#  message and passes the parsed data to the handler, then sends the result
#  back to the user
system_parse_mode = ParseMode.MARKDOWN_V2


def __init__(self):
    self.start_time = datetime.now()

    self.logger = loguru.logger.bind(component=self.__class__.__name__)
    # token = config.token.get_secret_value()

    # if config.parse_mode is not None:
    #     # Warn about broken features if parse_mode is not None
    #     self.logger.warning(
    #         "Custom default parse_mode is WIP "
    #         "and some features may not work as expected"
    #     )
    # aiogram
    # self._aiogram_bot: aiogram.Bot = aiogram.Bot(
    #     token=token  # , parse_mode=self.config.parse_mode  # plain text
    # )
    # self._dp: aiogram.Dispatcher = aiogram.Dispatcher(bot=self._aiogram_bot)
    # self._me = None


def register_command(self, handler, commands=None, description=None, filters=None):
    if filters is None:
        filters = ()
    if isinstance(commands, str):
        commands = [commands]
    self.logger.info(f"Registering command {commands}")
    commands = [c.lower() for c in commands]
    self._commands.extend([(c, description) for c in commands])
    self._dp.message.register(handler, Command(commands=commands), *filters)


_commands: List


@property
def commands(self) -> List[CommandRegistryItem]:
    return self._commands


NO_COMMAND_DESCRIPTION = "No description provided"


async def _set_aiogram_bot_commands(self):
    bot_commands = [
        types.BotCommand(command=c, description=d or self.NO_COMMAND_DESCRIPTION)
        for c, d in self.commands
    ]
    await self._aiogram_bot.set_my_commands(bot_commands)


@abstractmethod
async def bootstrap(self):
    self._me = await self._aiogram_bot.get_me()
    # todo: auto-add all commands marked with decorator
    for item in command_registry:
        handler = self.__getattribute__(item.handler_name)
        self.register_command(
            handler=handler,
            commands=item.commands,
            description=item.description,
            filters=item.filters,
        )


@property
def me(self):
    return self._me


async def run(self) -> None:
    await self.bootstrap()
    await self._set_aiogram_bot_commands()

    bot_name = (await self._aiogram_bot.get_me()).username
    bot_link = f"https://t.me/{bot_name}"
    self.logger.info(f"Starting telegram bot at {bot_link}")
    # And the run events dispatching
    await self._dp.start_polling(self._aiogram_bot)


# todo: app.run(...)
# async def download_large_file(self, chat_id, message_id):
#     async with self.pyrogram_client as app:
#         message = await app.get_messages(chat_id, message_ids=message_id)
#         return await message.download(in_memory=True)


command_registry: List[CommandRegistryItem] = []

Commands = Union[str, List[str]]


# use decorator to mark commands and parse automatically
def mark_command(commands: Commands, description: str = None, filters: list = None, dev=False):
    if isinstance(commands, str):
        commands = [commands]

    def wrapper(func):
        command_registry.append(
            CommandRegistryItem(
                commands=commands,
                handler_name=func.__name__,
                description=description,  # todo: use docstring by default
                filters=filters or (),
            )
        )

        @wraps(func)
        def wrapped(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapped

    return wrapper


_commands = []


def __init__(self, app: "App" = None, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.app = app

    # todo: rework to multi-chat state
    self._multi_message_mode = defaultdict(bool)
    self.messages_stack = defaultdict(list)
    self.errors = defaultdict(lambda: deque(maxlen=128))


# no decorator to control init order and user access
# @mark_command(commands=["start"], description="Start command")
# async def start(self, message: types.Message):
#     response = dedent(
#         f"""
#         Hi\! I'm the {self.__class__.__name__}\.
#         I'm based on the [bot\-base](https://github.com/calmmage/bot\-base) library\.
#         I support the following features:
#         \- voice messages parsing
#         \- hashtag and attribute recognition \(\#ignore, ignore\=True\)
#         \- multi\-message mode
#         Use /help for more details
#         """
#     )
#     await self.send_safe(
#         text=response,
#         chat_id=message.chat.id,
#         parse_mode=self.system_parse_mode,
#     )


# @mark_command(["help"], description="Show this help message")
async def help(self, message: types.Message):
    # todo: send a description / docstring of each command
    #  I think I already implemented this somewhere.. summary bot?
    #  automatically gather docstrings of all methods with @mark_command
    # todo: bonus: use gpt for help conversation
    reply_message = ""
    for command in self.commands:
        reply_message += f"/{command[0]} - {command[1]}\n"
    # todo: hide the dev commands
    await self.send_safe(
        text=reply_message,
        chat_id=message.chat.id,
        escape_markdown=True,
        parse_mode=self.system_parse_mode,
    )


def filter_unauthorised(self, message):
    username = message.from_user.username
    # self.logger.debug(f"checking user {username}")
    # self.logger.debug(f"Allowed users:  {self._config.allowed_users}")
    return username not in self.config.allowed_users


UNAUTHORISED_RESPONSE = dedent(
    """You are not authorized to use this bot.
    Available commands: /start, /help
    """
)


async def check_message_mentions_bot(self, message):
    message_text = await self._extract_message_text(message)
    bot_username = self.me.username
    return bot_username in message_text


async def check_message_uses_bot_command(self, message):
    message_text = await self._extract_message_text(message)
    if not message_text.startswith("/"):
        return False
    command = message_text.split(" ", 1)[0]
    return self.has_command(command)


# todo: test
def has_command(self, command):
    return any([command in c[0] for c in self.commands])


async def chat_message_handler(self, message: types.Message):
    """
    Placeholder implementation of main chat message handler
    Parse the message as the bot will see it and send it back
    Replace with your own implementation
    """
    message_text = await self._extract_message_text(message)
    self.logger.info("Received message", user=message.from_user.username, data=message_text)
    if self._multi_message_mode:
        self.messages_stack[message.chat.id].append(message)
    else:
        # todo: use "make_simple_command_handler" to create this demo

        data = self._parse_message_text(message_text)
        response = f"Message parsed: {json.dumps(data, ensure_ascii=False)}"
        await self.send_safe(
            text=response,
            chat_id=message.chat.id,
            reply_to_message_id=message.message_id,
        )

    return message_text


# ------------------------------------------------------------


@mark_command(commands=["multistart"], description="Start multi-message mode")
async def multi_message_start(self, message: types.Message):
    # activate multi-message mode
    chat_id = message.chat.id
    self._multi_message_mode[chat_id] = True
    self.logger.info("Multi-message mode activated", user=message.from_user.username)
    # todo: initiate timeout and if not deactivated - process messages
    #  automatically


@mark_command(commands=["multiend"], description="End multi-message mode")
async def multi_message_end(self, message: types.Message):
    # deactivate multi-message mode and process content
    chat_id = message.chat.id
    self._multi_message_mode[chat_id] = False
    self.logger.info(
        "Multi-message mode deactivated. Processing messages",
        user=message.from_user.username,
        data=str(self.messages_stack),
    )
    response = await self.process_messages_stack(chat_id)
    await message.answer(response)
    self.logger.info("Messages processed", user=message.from_user.username, data=response)


async def process_messages_stack(self, chat_id):
    """
    This is a placeholder implementation to demonstrate the feature
    :return:
    """
    data = await self._extract_stacked_messages_data(chat_id)
    response = f"Message parsed: {json.dumps(data)}"

    self.logger.info("Messages processed, clearing stack")
    self.messages_stack[chat_id] = []
    return response


async def _extract_stacked_messages_data(self, chat_id):
    if len(self.messages_stack) == 0:
        self.logger.info("No messages to process")
        return
    self.logger.info(f"Processing {len(self.messages_stack[chat_id])} messages")
    messages_text = ""
    for message in self.messages_stack[chat_id]:
        # todo: parse message content one by one.
        #  to support parsing of the videos and other applied modifiers
        messages_text += await self._extract_message_text(message)
    return self._parse_message_text(messages_text)


async def bootstrap(self):
    self.register_command(self.start, "start", "Start command")
    self.register_command(self.help, "help", "Help message")
    self._dp.error.register(self.error_handler, F.update.message.as_("message"))
    # self.register_command(self.error_command_handler, commands="error")
    self._dp.message.register(self.unauthorized, self.filter_unauthorised)
    await super().bootstrap()

    if self.config.test_mode:
        self.logger.debug("Running in test mode")
        self.register_command(self.test_send_file, commands="testfilesend")
        self.register_command(self.test_error_handler, commands="testerror")

    # admin commands
    # self.register_command(self.uptime, commands="devUptime")

    # dev
    # self.register_command(self.get_chat_id, commands="devGetChatId")

    # todo: simple message parsing
    self._dp.message.register(self.chat_message_handler)


# -----------------------------------------------------
# TEST MODE
# -----------------------------------------------------
async def test_send_file(self, message: types.Message):
    self.logger.debug("Received testfilesend command")
    await self._send_as_file(message.chat.id, "test text", message.message_id)


async def test_error_handler(self, message: types.Message):
    self.logger.debug("Received testerror command")
    raise Exception("TestError")


# @admin
@mark_command(commands="devUptime", description="Show bot uptime", dev=True)
async def uptime(self, message: types.Message):
    uptime = datetime.now() - self.start_time
    # await message.answer(f"Uptime: {uptime}")
    # todo: format uptime as human-readable string
    # e.g. 1 day, 2 hours, 3 minutes, 4 seconds
    # this is the code:
    await message.answer(f"Uptime: {uptime}")


# -----------------------------------------------------
# dev commands
# todo: can I set self-destruct timer on these commands?
# option 1: in config
# option 2: in class variable
# option 3: in constructor / init - attribute
# -----------------------------------------------------


@mark_command(commands="devGetChatId", dev=True, description="Show chat id")
async def get_chat_id(self, message: types.Message):
    reply = await message.answer(f"Chat id: {message.chat.id}")
    # todo: rework into decorator / apply to all dev commands
    await asyncio.sleep(self.config.dev_message_timeout)
    await reply.delete()
    await message.delete()


# -----------------------------------------------------
# easter eggs, experimental
# -----------------------------------------------------

_ping_replies_path = Path(__file__).parent / "ping_replies.txt"
try:
    ping_replies = _ping_replies_path.read_text().splitlines()
except:
    ping_replies = ["Failed to load fancy pongs, so you get this: Pong"]


@mark_command(commands="ping", description="Ping the bot")
async def ping_handler(self, message: types.Message):
    self.logger.debug("Received ping")
    # random choice from the list of replies
    message_text = random.choice(self.ping_replies)
    await self.send_safe(text=message_text, chat_id=message.chat.id)
