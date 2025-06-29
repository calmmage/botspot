import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Union

from aiogram import Bot, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InaccessibleMessage, InlineKeyboardButton, InlineKeyboardMarkup, Message
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger

logger = get_logger()


class AskUserSettings(BaseSettings):
    enabled: bool = True
    default_timeout: int = 1200

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
    timeout: Optional[float] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    notify_on_timeout: bool = True,
    default_choice: Optional[str] = None,
    return_raw: bool = False,
    cleanup: bool = False,
    **kwargs,
) -> Optional[Union[str, Message]]:
    """Base function for asking user questions with optional reply_markup"""
    from botspot.core.dependency_manager import get_dependency_manager

    # Check if question text is empty
    if not question or question.strip() == "":
        raise ValueError("Message text cannot be empty")

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
    assert request.event is not None

    sent_message = await bot.send_message(chat_id, question, reply_markup=reply_markup, **kwargs)
    assert sent_message.text is not None

    if timeout is None:
        timeout = deps.botspot_settings.ask_user.default_timeout
    if timeout == 0:
        # a way to specify no timeout
        timeout = None

    try:
        await asyncio.wait_for(request.event.wait(), timeout=timeout)
        if cleanup:
            # Delete both the question and the answer
            await sent_message.delete()
            if request.raw_response:
                await request.raw_response.delete()
        elif sent_message.reply_markup:
            # Remove buttons after getting response
            await sent_message.edit_text(text=sent_message.text, reply_markup=None)
        return (
            request.raw_response
            if (return_raw and (request.raw_response is not None))
            else request.response
        )
    except asyncio.TimeoutError:
        if notify_on_timeout:
            if default_choice is not None:
                question += f"\n\n⏰ Auto-selected: {default_choice}"
            else:
                question += "\n\n⏰ No response received within the time limit."
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
    cleanup: bool = False,
    **kwargs,
) -> Optional[str]:
    """
    Ask user a question and wait for text response

    Parameters:
        chat_id: ID of the chat to ask in
        question: Question text to send
        state: FSMContext for state management
        timeout: How long to wait for response (seconds)
        cleanup: Whether to delete both question and answer messages after getting response
    """
    return await _ask_user_base(chat_id, question, state, timeout, cleanup=cleanup, **kwargs)


async def ask_user_raw(
    chat_id: int,
    question: str,
    state: FSMContext,
    timeout: Optional[float] = 60.0,
    cleanup: bool = False,
    **kwargs,
) -> Optional[Message]:
    return await _ask_user_base(
        chat_id, question, state, timeout=timeout, return_raw=True, cleanup=cleanup, **kwargs
    )


async def ask_user_choice(
    chat_id: int,
    question: str,
    choices: Union[List[str], Dict[str, str]],
    state: FSMContext,
    timeout: Optional[float] = 60.0,
    default_choice: Optional[str] = None,
    highlight_default: bool = True,
    cleanup: bool = False,
    columns: Optional[int] = 1,
    **kwargs,
) -> Optional[str]:
    """
    Ask user to choose from options using inline buttons

    Parameters:
        chat_id: ID of the chat to ask in
        question: Question text to send
        choices: List of choices or Dict mapping callback data to display text
        state: FSMContext for state management
        timeout: How long to wait for response (seconds)
        default_choice: Choice to select if user doesn't respond
        cleanup: Whether to delete both question and answer messages after getting response
        columns: Number of buttons per row in the keyboard layout
        add_hint: Whether to add a hint about text input option
        **kwargs: Additional parameters passed to send_message
    """
    if isinstance(choices, list):
        choices = {choice: choice for choice in choices}

    # If default_choice not specified, use first option
    if default_choice is None and choices:
        default_choice = next(iter(choices.keys()))

    # Build keyboard with specified number of columns
    items = []
    rows = []

    for data, text in choices.items():
        button = InlineKeyboardButton(
            text=f"⭐ {text}" if highlight_default and (data == default_choice) else text,
            callback_data=f"choice_{data}",
        )
        items.append(button)

        if len(items) == columns:
            rows.append(items)
            items = []

    # Add any remaining items
    if items:
        rows.append(items)

    keyboard = InlineKeyboardMarkup(inline_keyboard=rows)

    return await _ask_user_base(
        chat_id=chat_id,
        question=question,
        state=state,
        timeout=timeout,
        reply_markup=keyboard,
        default_choice=default_choice,
        cleanup=cleanup,
        **kwargs,
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
    assert active_request.event is not None
    active_request.event.set()


async def ask_user_confirmation(
    chat_id: int,
    question: str,
    state: FSMContext,
    timeout: Optional[float] = 60.0,
    default_choice: Optional[bool] = True,
    cleanup: bool = False,
    **kwargs,
) -> Optional[bool]:
    """
    Ask user a yes/no confirmation question using inline buttons

    Parameters:
        chat_id: ID of the chat to ask in
        question: Question text to send
        state: FSMContext for state management
        timeout: How long to wait for response (seconds)
        default_choice: Default boolean choice (True=Yes, False=No) if user doesn't respond
        cleanup: Whether to delete both question and answer messages after getting response
        **kwargs: Additional parameters passed to send_message

    Returns:
        Boolean representing user's choice (True for Yes, False for No),
        or None if no response and no default
    """
    choices = {"yes": "Yes", "no": "No"}

    # Set default based on boolean parameter
    default = "yes" if default_choice else "no"

    result = await ask_user_choice(
        chat_id=chat_id,
        question=question,
        choices=choices,
        state=state,
        timeout=timeout,
        default_choice=default,
        cleanup=cleanup,
        **kwargs,
    )

    # Convert string result to boolean
    if result == "yes":
        return True
    elif result == "no":
        return False
    return None


async def ask_user_choice_raw(
    chat_id: int,
    question: str,
    choices: Union[List[str], Dict[str, str]],
    state: FSMContext,
    timeout: Optional[float] = 60.0,
    default_choice: Optional[str] = None,
    highlight_default: bool = True,
    cleanup: bool = False,
    add_hint: bool = False,
    columns: Optional[int] = 1,
    **kwargs,
) -> Optional[Message]:
    """
    Ask user to choose from options using inline buttons and return the raw Message object

    Parameters:
        chat_id: ID of the chat to ask in
        question: Question text to send
        choices: List of choices or Dict mapping callback data to display text
        state: FSMContext for state management
        timeout: How long to wait for response (seconds)
        default_choice: Choice to select if user doesn't respond
        cleanup: Whether to delete both question and answer messages after getting response
        add_hint: Whether to add a hint about text input option
        columns: Number of buttons per row in the keyboard layout
        **kwargs: Additional parameters passed to send_message

    Returns:
        The complete Message object containing the user's response
    """
    if isinstance(choices, list):
        choices = {choice: choice for choice in choices}

    # If default_choice not specified, use first option
    if default_choice is None and choices:
        default_choice = next(iter(choices.keys()))

    # Build keyboard with specified number of columns
    items = []
    rows = []

    for data, text in choices.items():
        button = InlineKeyboardButton(
            text=f"⭐ {text}" if highlight_default and (data == default_choice) else text,
            callback_data=f"choice_{data}",
        )
        items.append(button)

        if len(items) == columns:
            rows.append(items)
            items = []

    # Add any remaining items
    if items:
        rows.append(items)

    keyboard = InlineKeyboardMarkup(inline_keyboard=rows)

    # If adding hint is requested
    displayed_question = question
    if add_hint:
        displayed_question = (
            f"{question}\n\nTip: You can choose an option or type your own response."
        )

    return await _ask_user_base(
        chat_id=chat_id,
        question=displayed_question,
        state=state,
        timeout=timeout,
        reply_markup=keyboard,
        return_raw=True,
        cleanup=cleanup,
        **kwargs,
    )


async def handle_choice_callback(callback_query: types.CallbackQuery, state: FSMContext):
    assert callback_query.data is not None
    if not callback_query.data.startswith("choice_"):
        return

    assert callback_query.message is not None
    chat_id = callback_query.message.chat.id
    state_data = await state.get_data()
    handler_id = state_data.get("handler_id")

    active_request = input_manager.get_active_request(chat_id)
    if not active_request or active_request.handler_id != handler_id:
        await callback_query.answer("This choice is no longer valid.")
        return

    # Protection against multiple callbacks for the same request
    if active_request.response is not None:
        # Request already has a response, this is likely a retry
        await callback_query.answer("Your choice has already been recorded.")
        return

    choice = callback_query.data[7:]
    active_request.response = choice
    assert active_request.event is not None
    active_request.event.set()

    await callback_query.answer()
    assert not isinstance(callback_query.message, InaccessibleMessage)

    # Edit the message to remove buttons and show selection
    new_text = f"{callback_query.message.text}\n\nSelected: {choice}"
    try:
        await callback_query.message.edit_text(new_text)
    except Exception as e:
        logger.warning(f"Failed to edit message after choice selection: {e}")


def setup_dispatcher(dp):
    """Register message and callback handlers"""
    dp.message.register(handle_user_input, UserInputState.waiting)
    dp.message.register(
        handle_user_input,
        UserInputState.waiting,
        ~F.text.startswith("/"),  # Using magic filter to exclude commands
    )
    dp.callback_query.register(
        handle_choice_callback,
        lambda c: c.data and c.data.startswith("choice_"),
        UserInputState.waiting,
    )
