# todo: check / store allowed users from the database - with payment subscription mode or something
from collections import defaultdict
from datetime import datetime
from functools import wraps
from typing import Optional

from aiogram import Dispatcher
from aiogram.types import Message
from pydantic_settings import BaseSettings

from botspot.utils.common import get_logger

logger = get_logger()


class TrialModeSettings(BaseSettings):
    enabled: bool = False
    allowed_users: list[str] = []
    limit_per_user: Optional[int] = None
    global_limit: Optional[int] = None
    period_per_user: int = 24 * 60 * 60
    global_period: int = 24 * 60 * 60

    class Config:
        env_prefix = "NBL_TRIAL_MODE_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Usage tracking per user and per function
usage = defaultdict(lambda: defaultdict(list))


def format_remaining_time(seconds):
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def add_user_limit(limit=3, period=24 * 60 * 60):
    """
    Decorator to add a per-user trial mode limit to the command
    """
    from botspot.core.dependency_manager import get_dependency_manager

    def wrapper(func):
        @wraps(func)
        async def wrapped(message: Message, **kwargs):
            deps = get_dependency_manager()
            settings = deps.nbl_settings.trial_mode
            user = message.from_user.username or str(message.from_user.id)

            if user not in settings.allowed_users:
                current_time = datetime.now().timestamp()
                func_name = func.__name__

                # Check per-user limit for this specific function
                user_func_usage = [t for t in usage[user][func_name] if current_time - t < period]
                usage[user][func_name] = user_func_usage

                if len(user_func_usage) >= limit:
                    remaining_seconds = int(user_func_usage[0] + period - current_time)
                    remaining_time = format_remaining_time(remaining_seconds)
                    await message.answer(
                        f"You have reached your usage limit for the {func_name} command. Reset in: {remaining_time}."
                    )
                    return

                usage[user][func_name].append(current_time)

            result = await func(message, **kwargs)
            return result

        return wrapped

    return wrapper


def add_global_limit(limit=100, period=24 * 60 * 60):
    """
    Decorator to add a global usage limit to the command
    """
    global_usage = []

    def wrapper(func):
        @wraps(func)
        async def wrapped(message: Message, **kwargs):
            current_time = datetime.now().timestamp()

            # Check global limit
            nonlocal global_usage
            global_usage = [t for t in global_usage if current_time - t < period]

            if len(global_usage) >= limit:
                remaining_seconds = int(global_usage[0] + period - current_time)
                remaining_time = format_remaining_time(remaining_seconds)
                await message.answer(
                    f"The {func.__name__} command has reached its global usage limit. Please try again later. Reset in: {remaining_time}."
                )
                return

            global_usage.append(current_time)

            result = await func(message, **kwargs)
            return result

        return wrapped

    return wrapper


class UsageLimitMiddleware:
    def __init__(self, limit_per_user=3, global_limit=100, period_per_user=24 * 60 * 60, global_period=24 * 60 * 60):
        self.limit_per_user = limit_per_user
        self.global_limit = global_limit
        self.period_per_user = period_per_user
        self.global_period = global_period
        self.user_usage = defaultdict(list)
        self.global_usage = []

    async def __call__(self, handler, event, data):
        current_time = datetime.now().timestamp()
        user_id = event.from_user.id if hasattr(event, "from_user") else None

        # Update global usage list
        self.global_usage = [t for t in self.global_usage if current_time - t < self.global_period]

        if self.global_limit and (len(self.global_usage) >= self.global_limit):
            message = event.message if hasattr(event, "message") else event
            remaining_seconds = int(self.global_usage[0] + self.global_period - current_time)
            remaining_time = format_remaining_time(remaining_seconds)

            await message.answer(
                f"The bot has reached its global usage limit. Please try again later. Reset in: {remaining_time}."
            )
            return

        if user_id and self.limit_per_user:
            # Update user usage list
            self.user_usage[user_id] = [t for t in self.user_usage[user_id] if current_time - t < self.period_per_user]

            if len(self.user_usage[user_id]) >= self.limit_per_user:
                message = event.message if hasattr(event, "message") else event

                remaining_seconds = int(self.user_usage[user_id][0] + self.period_per_user - current_time)
                remaining_time = format_remaining_time(remaining_seconds)
                await message.answer(
                    f"You have reached your personal usage limit. Please try again later. Reset in: {remaining_time}."
                )
                return

            self.user_usage[user_id].append(current_time)

        self.global_usage.append(current_time)

        return await handler(event, data)


def setup_dispatcher(dp: Dispatcher, limit_per_user=None, global_limit=None, period_per_user=None, global_period=None):
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    settings = deps.nbl_settings.trial_mode
    limit_per_user = limit_per_user or settings.limit_per_user
    global_limit = global_limit or settings.global_limit
    period_per_user = period_per_user or settings.period_per_user
    global_period = global_period or settings.global_period
    # You can add any necessary setup for the trial mode here
    middleware = UsageLimitMiddleware(
        limit_per_user=limit_per_user,
        global_limit=global_limit,
        period_per_user=period_per_user,
        global_period=global_period,
    )
    dp.message.middleware(middleware)
    dp.callback_query.middleware(middleware)

    logger.info(f"Router set up with usage limits: per-user={limit_per_user}, global={global_limit}")

    return dp
