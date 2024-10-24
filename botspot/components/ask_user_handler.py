import asyncio
from datetime import datetime
from typing import Optional, Dict, Union, List

from aiogram import types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from botspot.utils.common import get_logger

logger = get_logger()


class AskUserSettings(BaseSettings):
    enabled: bool = True

    class Config:
        env_prefix = "NBL_ASK_USER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class UserInputState(StatesGroup):
    waiting = State()  # Generic waiting state


class PendingRequest(BaseModel):
    question: str
    handler_id: str
    created_at: datetime = datetime.now()  # Default value
    event: Optional[asyncio.Event] = None  # Will be set in constructor
    response: Optional[str] = None

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

        self._pending_requests[chat_id][handler_id] = PendingRequest(question=question, handler_id=handler_id)

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
) -> Optional[str]:
    """Base function for asking user questions with optional keyboard"""
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    bot: Bot = deps.bot

    handler_id = f"ask_{id(question)}_{datetime.now().timestamp()}"

    # Store state data
    await state.set_state(UserInputState.waiting)
    await state.update_data(handler_id=handler_id)

    # Add request to manager
    input_manager.add_request(chat_id, handler_id, question)

    # Get the request object
    request = input_manager.get_active_request(chat_id)
    if not request:
        logger.error("Failed to create request")
        return None

    # Send question
    await bot.send_message(chat_id, question, reply_markup=keyboard)

    try:
        await asyncio.wait_for(request.event.wait(), timeout=timeout)
        return request.response
    except asyncio.TimeoutError:
        await bot.send_message(chat_id, "No response received within the time limit.")
        return None
    finally:
        input_manager.remove_request(chat_id, handler_id)
        await state.clear()


async def ask_user(chat_id: int, question: str, state: FSMContext, timeout: Optional[float] = 60.0) -> Optional[str]:
    """Ask user a question and wait for text response"""
    return await _ask_user_base(chat_id, question, state, timeout)


async def ask_user_choice(
    chat_id: int,
    question: str,
    choices: Union[List[str], Dict[str, str]],
    state: FSMContext,
    timeout: Optional[float] = 60.0,
) -> Optional[str]:
    """Ask user to choose from options using inline buttons"""
    if isinstance(choices, list):
        choices = {choice: choice for choice in choices}

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=f"choice_{data}")] for data, text in choices.items()
        ]
    )

    return await _ask_user_base(chat_id, question, state, timeout, keyboard)


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
            chat_id, "Sorry, this response came too late or was for a different question. Please try again."
        )
        await state.clear()
        return

    active_request.response = message.text
    active_request.event.set()


async def handle_choice_callback(callback_query: types.CallbackQuery, state: FSMContext):
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
    await callback_query.message.edit_reply_markup(reply_markup=None)


def setup_dispatcher(dp):
    """Register message and callback handlers"""
    dp.message.register(handle_user_input, UserInputState.waiting)
    dp.callback_query.register(
        handle_choice_callback, lambda c: c.data and c.data.startswith("choice_"), UserInputState.waiting
    )
