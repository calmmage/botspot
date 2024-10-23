import asyncio
from collections import defaultdict

from aiogram import Dispatcher
from aiogram.types import Message
from pydantic_settings import BaseSettings

# from dev.draft.easter_eggs.main import get_easter_egg
from dev.draft.lib_files.utils.common import get_logger

logger = get_logger()


class MultiForwardHandlingSettings(BaseSettings):
    enabled: bool = True

    # easter_eggs: bool = True

    class Config:
        env_prefix = "ERROR_HANDLING_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class MyApp:
    pass


# todo: store this better? in User data?
user_message_queue = defaultdict(asyncio.Queue)
user_lock = defaultdict(asyncio.Lock)
# self.chat_handler_ignore_commands = True

# 500 ms delay
MULTI_MESSAGE_DELAY = 0.5

has_chat_handler = True


# multi_message_handler
async def chat_handler(self, message: Message, app: MyApp):
    user = self.get_user(message)
    queue = app.user_message_queue[user]
    await queue.put(message)

    # try to grab the lock
    async with app.user_lock[user]:
        # wait for the delay
        await asyncio.sleep(self.MULTI_MESSAGE_DELAY)

        # grab all the messages from the queue
        messages = []
        while not queue.empty():
            item = await queue.get()
            messages.append(item)
        if not messages:
            self.logger.debug("Aborting message processing. Messages got processed by another handler.")
            return
        if self.chat_handler_ignore_commands:
            messages.sort(key=lambda x: x.date)
            if messages[0].text.startswith("/"):
                self.logger.debug("Found a command, aborting")
                for message in messages:
                    await queue.put(message)
                return
        # test: send user the message count
        await message.answer(f"Received {len(messages)} messages")

        text = await self.compose_messages(messages)
        if self.send_as_file:
            # chat_id, text, reply_to_message_id=None, filename=None
            # todo: add caption with '/export' command
            #  when i implement it
            await self._send_as_file(message.chat.id, text, filename="messages.txt")
        else:
            await self.reply_safe(message, text)


# format date as hh:mm
async def compose_messages(
        self,
        messages,
        include_usernames=True,
        include_timestamps=True,
        date_format="[%H:%M]",
        separator="\n\n~~~\n\n",
        # separator="\n\n",
):
    text = ""
    for message in messages:
        parts = []
        if include_timestamps:
            parts += [message.date.strftime(date_format)]
        if include_usernames:
            name = self.get_name(message, forward_priority=True)
            if name:
                parts += [name]
            else:
                user = self.get_user(message, forward_priority=True)
                parts += [f"@{user}"]
        if parts:
            text += " ".join(parts) + ":\n"
        try:
            text += await self._extract_message_text(message)
            text += separator
        except:
            self.logger.exception("Failed to extract message text")
            text += f"Failed to extract message text\n{separator}"
    return text


def multimessage_command_handler(self, handler):
    async def func(message: Message, app: MyApp):

        user = self.get_user(message)
        queue = app.user_message_queue[user]
        await queue.put(message)

        # try to grab the lock
        async with app.user_lock[user]:
            # wait for the delay
            await asyncio.sleep(self.MULTI_MESSAGE_DELAY)

            # grab all the messages from the queue
            messages = []
            while not queue.empty():
                item = await queue.get()
                messages.append(item)
            if not messages:
                raise Exception("Messages got processed by another handler, should not happen with commands")
            # test: send user the message count
            await handler.multi_message_handler(messages, app)

    return func


async def set_send_as_file(self, message: Message, app: MyApp):
    text = message.text
    text = self.strip_command(text)
    if text.lower() in ["0", "false", "no", "off", "disable"]:
        self.send_as_file = False
        await message.answer("Send as file disabled")
    else:
        self.send_as_file = True
        await message.answer("Send as file enabled")


async def enable_send_as_file(self, message: Message, app: MyApp):
    self.send_as_file = True
    await message.answer("Send as file enabled")


async def disable_send_as_file(self, message: Message, app: MyApp):
    self.send_as_file = False
    await message.answer("Send as file disabled")


async def multi_forward_handler():
    """
    log error to the logger
    also send a message to the user
    """
    from dev.draft.lib_files.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()


def setup_dispatcher(dp: Dispatcher):
    dp.message.register(multi_forward_handler)
