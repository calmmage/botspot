from pydantic_settings import BaseSettings


class AskUserSettings(BaseSettings):
    enabled: bool = True

    class Config:
        env_prefix = "NBL_ASK_USER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message

from botspot.utils.common import get_logger

logger = get_logger()


class UserInputState(StatesGroup):
    waiting = State()  # Generic waiting state


@dataclass
class PendingRequest:
    question: str
    created_at: datetime
    handler_id: str  # Unique ID for each request


class UserInputManager:
    def __init__(self):
        self._pending_requests: Dict[int, Dict[str, PendingRequest]] = {}

    def add_request(self, chat_id: int, handler_id: str, question: str) -> None:
        if chat_id not in self._pending_requests:
            self._pending_requests[chat_id] = {}

        self._pending_requests[chat_id][handler_id] = PendingRequest(
            question=question, created_at=datetime.now(), handler_id=handler_id
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


async def ask_user(message: Message, question: str, state: FSMContext) -> str:
    """
    Ask user a question and wait for their response.
    Returns the user's response text.
    """
    chat_id = message.chat.id
    handler_id = f"ask_{id(question)}_{datetime.now().timestamp()}"

    # Store state data
    await state.set_state(UserInputState.waiting)
    await state.update_data(handler_id=handler_id)

    # Add request to manager
    input_manager.add_request(chat_id, handler_id, question)

    # Send question
    await message.answer(question)

    # Wait for response via state
    try:
        response = await state.get_data()
        return response.get("response", "")
    finally:
        # Cleanup
        input_manager.remove_request(chat_id, handler_id)
        await state.clear()


async def handle_user_input(message: Message, state: FSMContext) -> None:
    """Handler for user responses"""
    if not await state.get_state() == UserInputState.waiting:
        return

    chat_id = message.chat.id
    state_data = await state.get_data()
    handler_id = state_data.get("handler_id")

    active_request = input_manager.get_active_request(chat_id)
    if not active_request or active_request.handler_id != handler_id:
        # This response is for a different/expired request
        await message.answer("Sorry, this response came too late or was for a different question. Please try again.")
        await state.clear()
        return

    # Store response in state
    await state.update_data(response=message.text)


def setup_dispatcher(dp):
    """Register message handler for user inputs"""
    dp.message.register(handle_user_input, UserInputState.waiting)
