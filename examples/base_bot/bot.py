from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from calmlib.utils import setup_logger
from dotenv import load_dotenv
from loguru import logger

from botspot.core.bot_manager import BotManager

from .app import App
from .router import router


def main(routers=(router,), AppClass=App):
    load_dotenv()

    app = AppClass()
    # Initialize bot and dispatcher
    dp = Dispatcher(app=app)

    if not isinstance(routers, (list, tuple)):
        routers = [routers]

    for router in routers:
        dp.include_router(router)

    bot = Bot(
        token=app.config.telegram_bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    setup_logger(logger)
    # Setup bot manager with basic components
    bm = BotManager(bot=bot)
    bm.setup_dispatcher(dp)

    # Start polling
    dp.run_polling(bot)


if __name__ == "__main__":
    main(routers=[router])
