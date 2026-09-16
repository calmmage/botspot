"""Message aggregator demo.

Forward a bunch of messages (or send a media album) and the bot reports them back as a single
batch — counting text messages and media attachments. Shows how `get_message_aggregator()`
collapses a burst into one ordered batch and how `get_message_attachments()` pulls media out.

Run:
    BOTSPOT_MESSAGE_AGGREGATOR_ENABLED=true python bot.py
"""

from aiogram import Dispatcher, Router
from aiogram.types import Message

from botspot import get_message_aggregator
from botspot.core.bot_manager import BotManager
from botspot.utils import get_message_attachments, send_safe

router = Router()


@router.message()
async def aggregate(message: Message):
    batch = await get_message_aggregator().collect(message)
    if batch is None:
        return  # this message was folded into a batch owned by an earlier call

    n_text = sum(1 for m in batch if (m.text or m.caption))
    n_media = sum(len(get_message_attachments(m)) for m in batch)
    await send_safe(
        message.chat.id,
        f"Captured a batch of <b>{len(batch)}</b> message(s): "
        f"{n_text} with text, {n_media} media attachment(s).",
    )


def main():
    from aiogram import Bot
    from botspot.core.botspot_settings import BotspotSettings

    dp = Dispatcher()
    dp.include_router(router)
    settings = BotspotSettings()
    settings.message_aggregator.enabled = True
    bot = Bot(token=__import__("os").environ["TELEGRAM_BOT_TOKEN"])
    bm = BotManager(bot=bot, **settings.model_dump())
    bm.setup_dispatcher(dp)
    dp.run_polling(bot)


if __name__ == "__main__":
    main()
