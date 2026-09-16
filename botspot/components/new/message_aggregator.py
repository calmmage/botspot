"""Message aggregator — collect bursts of messages into a single ordered batch.

When a user forwards many messages at once (or sends a media album), Telegram delivers
them as many separate updates. This component debounces them into one batch so a handler
can process the whole burst together — text, media albums and all.

Usage inside a (catch-all) message handler::

    from botspot import get_message_aggregator

    @router.message()
    async def handle(message: Message):
        batch = await get_message_aggregator().collect(message)
        if batch is None:
            return  # folded into a batch an earlier call already owns
        # `batch` is the full ordered list of Messages in the burst
        ...

Media albums are handled for free: the messages of an album share a ``media_group_id`` and
arrive within milliseconds, so the debounce window collects them together. Use
``botspot.utils.get_message_attachments`` / ``download_telegram_file`` on each message to pull
the actual media out.
"""

import asyncio
from collections import defaultdict
from typing import Dict, List, Optional

from aiogram import Dispatcher
from aiogram.types import Message
from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger

logger = get_logger()


class MessageAggregatorSettings(BaseSettings):
    enabled: bool = False
    # seconds to wait for more messages before sealing a batch
    delay: float = 1.0
    # if a burst starts with a command, leave it for normal command handlers
    ignore_commands: bool = True

    class Config:
        env_prefix = "BOTSPOT_MESSAGE_AGGREGATOR_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


def _default_key(message: Message):
    """Aggregate per-user, falling back to chat (e.g. channel posts)."""
    if message.from_user:
        return message.from_user.id
    return message.chat.id


class MessageAggregator:
    def __init__(self, settings: MessageAggregatorSettings):
        self.settings = settings
        self._queues: Dict[object, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._locks: Dict[object, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def collect(
        self,
        message: Message,
        *,
        key: Optional[object] = None,
        delay: Optional[float] = None,
    ) -> Optional[List[Message]]:
        """Fold ``message`` into the current burst.

        Returns the full, time-ordered batch for the FIRST call that drains the burst, and
        ``None`` for every other message folded into that same batch (those calls should
        just return — the batch is owned by the draining call).
        """
        if key is None:
            key = _default_key(message)
        if delay is None:
            delay = self.settings.delay

        queue = self._queues[key]
        await queue.put(message)

        # Only one call per key proceeds past the debounce at a time; it drains everything
        # that landed in the queue during the wait. Siblings find an empty queue -> None.
        async with self._locks[key]:
            await asyncio.sleep(delay)

            messages: List[Message] = []
            while not queue.empty():
                messages.append(queue.get_nowait())
            if not messages:
                logger.debug("message_aggregator: burst already drained by a sibling call")
                return None

            messages.sort(key=lambda m: (m.date, m.message_id))

            if (
                self.settings.ignore_commands
                and messages[0].text
                and messages[0].text.startswith("/")
            ):
                logger.debug("message_aggregator: burst starts with a command, releasing it")
                return None

            logger.debug(f"message_aggregator: sealed a batch of {len(messages)} message(s)")
            return messages


def setup_dispatcher(dp: Dispatcher):
    # The aggregator is driven by the bot's own handler via collect(); nothing to register.
    return dp


def initialize(settings: MessageAggregatorSettings) -> MessageAggregator:
    if not settings.enabled:
        logger.info("MessageAggregator component is disabled")
    else:
        logger.info("MessageAggregator component initialized")
    return MessageAggregator(settings)


def get_message_aggregator() -> "MessageAggregator":
    from botspot.core.dependency_manager import get_dependency_manager

    return get_dependency_manager().message_aggregator
