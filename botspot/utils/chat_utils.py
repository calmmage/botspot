from contextlib import asynccontextmanager


@asynccontextmanager
async def typing_status(chat_id: int):
    """Context manager for handling typing status in Telegram chat.

    Args:
        chat_id: The chat ID to show typing status in

    Example:
        async with typing_status(chat_id):
            # Do some work
            await some_long_operation()
    """
    from botspot.utils.deps_getters import get_bot

    bot = get_bot()
    try:
        await bot.send_chat_action(chat_id, "typing")
        yield
    finally:
        await bot.send_chat_action(chat_id, "cancel")
