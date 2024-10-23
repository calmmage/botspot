# from aiogram.types import Message
from typing import Optional
from aiogram.types import Message
from dev.draft.lib_files.dependency_manager import DependencyManager, get_dependency_manager


async def send_safe(chat_id, text, deps: DependencyManager = None, reply_to_message_id: Optional[int] = None, **kwargs):
    """
    Send message with safe mode
    :param chat_id:
    :param text:
    :param kwargs:
    :return:
    """
    # todo: include old send_safe logic
    if deps is None:
        deps = get_dependency_manager()
    bot = deps.bot
    await bot.send_message(chat_id, text, reply_to_message_id=reply_to_message_id, **kwargs)


# async def forward_message(message: Message, chat_id, **kwargs, deps: DependencyManager = None):
#     await message.forward(chat_id)


async def reply_safe(message: Message, text: str, **kwargs):
    await send_safe(message.chat.id, text, reply_to_message_id=message.message_id, **kwargs)


async def answer_safe(message: Message, text: str, **kwargs):
    await send_safe(message.chat.id, text, **kwargs)
