import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Union

from aiogram import Bot, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger

logger = get_logger()


class AskUserSettings(BaseSettings):
    enabled: bool = True

    class Config:
        env_prefix = "BOTSPOT_ASK_USER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class UserInputState(StatesGroup):
    waiting = State()  # Generic waiting state


class PendingRequest(BaseModel):
    question: str
    handler_id: str
    created_at: datetime = datetime.now()
    event: Optional[asyncio.Event] = None
    response: Optional[str] = None
    raw_response: Optional[Message] = None

    class Config:
        arbitrary_types_allowed = True  # Needed for asyncio.Event

    def __init__(self, **data):
        super().__init__(**data)
        if self.event is None:
            self.event = asyncio.Event()


class UserInputManager:
    def __init__(self):
        self._pending_requests: Dict[int, Dict[str, PendingRequest]] = {}

    def add_request(self, chat_id: int, handler_id: str, question: str) -> None:
        if chat_id not in self._pending_requests:
            self._pending_requests[chat_id] = {}

        self._pending_requests[chat_id][handler_id] = PendingRequest(
            question=question, handler_id=handler_id
        )

    def get_active_request(self, chat_id: int) -> Optional[PendingRequest]:
        if chat_id not in self._pending_requests:
            return None
        # Get the oldest pending request
        requests = self._pending_requests[chat_id]
        if not requests:
            return None
        return min(requests.values(), key=lambda x: x.created_at)

    def remove_request(self, chat_id: int, handler_id: str) -> None:
        if chat_id in self._pending_requests:
            self._pending_requests[chat_id].pop(handler_id, None)
            if not self._pending_requests[chat_id]:
                del self._pending_requests[chat_id]


# Global instance
input_manager = UserInputManager()


async def _ask_user_base(
    chat_id: int,
    question: str,
    state: FSMContext,
    timeout: Optional[float] = 60.0,
    keyboard: Optional[InlineKeyboardMarkup] = None,
    notify_on_timeout: bool = True,
        default_choice: Optional[str] = None,
        return_raw: bool = False,
        # message_ref: Optional[types.Message] = None,
) -> Optional[Union[str, Message]]:
    """Base function for asking user questions with optional keyboard"""
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    bot: Bot = deps.bot

    handler_id = f"ask_{id(question)}_{datetime.now().timestamp()}"

    if default_choice is not None and return_raw:
        raise ValueError(
            "Cannot return default choice when return_raw is True - conflict of return types"
        )

    await state.set_state(UserInputState.waiting)
    await state.update_data(handler_id=handler_id)

    input_manager.add_request(chat_id, handler_id, question)

    request = input_manager.get_active_request(chat_id)
    if not request:
        logger.error("Failed to create request")
        return None

    sent_message = await bot.send_message(chat_id, question, reply_markup=keyboard)

    try:
        await asyncio.wait_for(request.event.wait(), timeout=timeout)
        return request.raw_response if return_raw else request.response
    except asyncio.TimeoutError:
        if notify_on_timeout:
            if default_choice is not None:
                question += f"\n\n⏰ Auto-selected: {default_choice}"
            else:
                question += f"\n\n⏰ No response received within the time limit."
            await sent_message.edit_text(question)
        return default_choice  # None if no default choice
    finally:
        input_manager.remove_request(chat_id, handler_id)
        await state.clear()


async def ask_user(
        chat_id: int,
        question: str,
        state: FSMContext,
        timeout: Optional[float] = 60.0,
        return_raw: bool = False,
) -> Optional[Union[str, Message]]:
    """Ask user a question and wait for text response"""
    return await _ask_user_base(
        chat_id, question, state, timeout, return_raw=return_raw
    )


async def ask_user_choice(
    chat_id: int,
    question: str,
    choices: Union[List[str], Dict[str, str]],
    state: FSMContext,
    timeout: Optional[float] = 60.0,
        default_choice: Optional[str] = None,
) -> Optional[str]:
    """Ask user to choose from options using inline buttons"""
    if isinstance(choices, list):
        choices = {choice: choice for choice in choices}

    # If default_choice not specified, use first option
    if default_choice is None and choices:
        default_choice = next(iter(choices.keys()))

    # Add star to default choice text
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"⭐ {text}" if data == default_choice else text,
                    callback_data=f"choice_{data}",
                )
            ]
            for data, text in choices.items()
        ]
    )

    return await _ask_user_base(
        chat_id=chat_id,
        question=question,
        state=state,
        timeout=timeout,
        keyboard=keyboard,
        default_choice=default_choice,
    )


async def handle_user_input(message: types.Message, state: FSMContext) -> None:
    """Handler for user responses"""
    from botspot.core.dependency_manager import get_dependency_manager

    if not await state.get_state() == UserInputState.waiting:
        return

    chat_id = message.chat.id
    state_data = await state.get_data()
    handler_id = state_data.get("handler_id")

    active_request = input_manager.get_active_request(chat_id)
    if not active_request or active_request.handler_id != handler_id:
        deps = get_dependency_manager()
        bot: Bot = deps.bot
        await bot.send_message(
            chat_id,
            "Sorry, this response came too late or was for a different question. Please try again.",
        )
        await state.clear()
        return

    active_request.raw_response = message
    active_request.response = message.text
    active_request.event.set()


async def handle_choice_callback(
        callback_query: types.CallbackQuery, state: FSMContext
):
    if not callback_query.data.startswith("choice_"):
        return

    chat_id = callback_query.message.chat.id
    state_data = await state.get_data()
    handler_id = state_data.get("handler_id")

    active_request = input_manager.get_active_request(chat_id)
    if not active_request or active_request.handler_id != handler_id:
        await callback_query.answer("This choice is no longer valid.")
        return

    choice = callback_query.data[7:]
    active_request.response = choice
    active_request.event.set()

    await callback_query.answer()
    new_text = f"{callback_query.message.text}\n\nSelected: {choice}"
    await callback_query.message.edit_text(new_text)


def setup_dispatcher(dp):
    """Register message and callback handlers"""
    dp.message.register(handle_user_input, UserInputState.waiting)
    dp.callback_query.register(
        handle_choice_callback,
        lambda c: c.data and c.data.startswith("choice_"),
        UserInputState.waiting,
    )
