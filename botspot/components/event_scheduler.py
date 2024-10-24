from typing import TYPE_CHECKING

from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = get_logger()


class EventSchedulerSettings(BaseSettings):
    enabled: bool = False

    # chat_id: int  # ID of the chat to send messages to

    class Config:
        env_prefix = "NBL_SCHEDULER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# scheduler_settings = SchedulerSettings()
# scheduler = AsyncIOScheduler()

# todo: this actually has nothing to do with dispatcher. move to bot.py
# async def scheduled_job(bot: Bot):
#     now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#     logger.info(f"Scheduled job executed at {now}")
#     await bot.send_message(
#         chat_id=scheduler_settings.chat_id,
#         text=f"Scheduled message at {now}"
#     )

# todo: this actually has nothing to do with dispatcher. move to bot.py
# def setup_dispatcher(dp: Dispatcher):
#     if not scheduler_settings.enabled:
#         logger.info("Scheduler is disabled.")
#         return

#     scheduler.add_job(
#         scheduled_job,
#         'interval',
#         minutes=1,
#         args=[dp.bot]
#     )
#     scheduler.start()
#     logger.info("Scheduler started.")


def setup_dispatcher(dp):
    # return dp
    pass


def initialise(settings: EventSchedulerSettings) -> "AsyncIOScheduler":
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    if not settings.enabled:
        logger.info("Event scheduler is disabled.")
        return None

    scheduler = AsyncIOScheduler()
    return scheduler
