import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Chat, InlineKeyboardMarkup, Message

from botspot.components.features.user_interactions import (
    UserInputState,
    _ask_user_base,
    ask_user_choice,
    handle_choice_callback,
    handle_user_input,
    input_manager,
)


@pytest.fixture
def mock_bot():
    bot = AsyncMock(spec=Bot)
    bot.send_message = AsyncMock(return_value=MagicMock(spec=Message))
    bot.send_message.return_value.text = "Test question"
    bot.send_message.return_value.message_id = 123
    bot.send_message.return_value.edit_text = AsyncMock()
    bot.send_message.return_value.delete = AsyncMock()
    return bot


@pytest.fixture
def mock_deps(mock_bot):
    with patch("botspot.core.dependency_manager.get_dependency_manager") as mock_get_deps:
        deps = MagicMock()
        deps.bot = mock_bot
        mock_get_deps.return_value = deps
        yield deps


@pytest.fixture
def mock_state():
    state = AsyncMock(spec=FSMContext)
    state.set_state = AsyncMock()
    state.update_data = AsyncMock()
    state.get_data = AsyncMock(return_value={"handler_id": "test_handler"})
    state.get_state = AsyncMock(return_value=UserInputState.waiting)
    state.clear = AsyncMock()
    return state


@pytest.fixture
def mock_message():
    message = MagicMock(spec=Message)
    message.text = "Test response"
    message.message_id = 456
    message.chat = MagicMock(spec=Chat)
    message.chat.id = 789
    message.delete = AsyncMock()
    message.edit_text = AsyncMock()
    return message


@pytest.fixture
def mock_callback_query():
    callback = MagicMock(spec=CallbackQuery)
    callback.data = "choice_option1"
    callback.message = MagicMock(spec=Message)
    callback.message.chat = MagicMock(spec=Chat)
    callback.message.chat.id = 789
    callback.message.text = "Test question"
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    return callback


@pytest.fixture(autouse=True)
def clear_input_manager():
    # Clear the input manager before each test
    input_manager._pending_requests = {}
    yield
    # Clear after test too
    input_manager._pending_requests = {}


class TestAskUserBase:
    @pytest.mark.asyncio
    async def test_successful_response(self, mock_deps, mock_state, mock_message):
        # Setup
        chat_id = 789
        question = "Test question"

        # Fix the mock to return a message properly
        mock_sent_message = MagicMock(spec=Message)
        mock_sent_message.text = question
        # Set reply_markup to trigger the edit_text call
        mock_sent_message.reply_markup = MagicMock(spec=InlineKeyboardMarkup)
        mock_sent_message.edit_text = AsyncMock()
        mock_deps.bot.send_message.return_value = mock_sent_message

        # Simulate user responding
        async def simulate_response():
            request = input_manager.get_active_request(chat_id)
            request.response = "Test response"
            request.raw_response = mock_message
            request.event.set()

        # Schedule response simulation
        asyncio.create_task(simulate_response())

        # Call function
        response = await _ask_user_base(
            chat_id=chat_id,
            question=question,
            state=mock_state,
            timeout=1.0,
        )

        # Assertions
        assert response == "Test response"
        mock_state.set_state.assert_called_once_with(UserInputState.waiting)
        mock_state.update_data.assert_called_once()
        mock_state.clear.assert_called_once()

        # Verify buttons were removed
        mock_deps.bot.send_message.return_value.edit_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_timeout(self, mock_deps, mock_state):
        # Setup
        chat_id = 789
        question = "Test question"

        # Call function with short timeout - will timeout as no response is sent
        response = await _ask_user_base(
            chat_id=chat_id,
            question=question,
            state=mock_state,
            timeout=0.1,
            notify_on_timeout=True,
        )

        # Assertions
        assert response is None
        mock_deps.bot.send_message.return_value.edit_text.assert_called_once()
        assert (
            "No response received within the time limit"
            in mock_deps.bot.send_message.return_value.edit_text.call_args[0][0]
        )

    @pytest.mark.asyncio
    async def test_default_choice_on_timeout(self, mock_deps, mock_state):
        # Setup
        chat_id = 789
        question = "Test question"
        default_choice = "default_option"

        # Call function with timeout and default choice
        response = await _ask_user_base(
            chat_id=chat_id,
            question=question,
            state=mock_state,
            timeout=0.1,
            notify_on_timeout=True,
            default_choice=default_choice,
        )

        # Assertions
        assert response == default_choice
        mock_deps.bot.send_message.return_value.edit_text.assert_called_once()
        assert (
            f"Auto-selected: {default_choice}"
            in mock_deps.bot.send_message.return_value.edit_text.call_args[0][0]
        )


class TestHandleUserInput:
    @pytest.mark.asyncio
    async def test_valid_input(self, mock_state, mock_message):
        # Setup - register a pending request
        chat_id = 789
        handler_id = "test_handler"
        input_manager.add_request(chat_id, handler_id, "Test question")

        # Call function
        await handle_user_input(mock_message, mock_state)

        # Check request was processed
        request = input_manager.get_active_request(chat_id)
        assert request.response == "Test response"
        assert request.event.is_set()


class TestHandleChoiceCallback:
    @pytest.mark.asyncio
    async def test_valid_choice(self, mock_state, mock_callback_query):
        # Setup - register a pending request
        chat_id = 789
        handler_id = "test_handler"
        input_manager.add_request(chat_id, handler_id, "Test question")

        # Call function
        await handle_choice_callback(mock_callback_query, mock_state)

        # Check request was processed
        request = input_manager.get_active_request(chat_id)
        assert request.response == "option1"
        assert request.event.is_set()

        # Check UI was updated
        mock_callback_query.answer.assert_called_once()
        mock_callback_query.message.edit_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_already_responded(self, mock_state, mock_callback_query):
        # Setup - register a pending request that already has a response
        chat_id = 789
        handler_id = "test_handler"
        input_manager.add_request(chat_id, handler_id, "Test question")

        # Set response before handling callback
        request = input_manager.get_active_request(chat_id)
        request.response = "previous_response"

        # Call function
        await handle_choice_callback(mock_callback_query, mock_state)

        # Verify original response wasn't changed
        assert request.response == "previous_response"

        # Check proper message was shown
        mock_callback_query.answer.assert_called_once_with("Your choice has already been recorded.")
        mock_callback_query.message.edit_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_handler(self, mock_state, mock_callback_query):
        # Setup with wrong handler ID
        mock_state.get_data.return_value = {"handler_id": "wrong_handler"}
        chat_id = 789
        handler_id = "test_handler"
        input_manager.add_request(chat_id, handler_id, "Test question")

        # Call function
        await handle_choice_callback(mock_callback_query, mock_state)

        # Verify error message
        mock_callback_query.answer.assert_called_once_with("This choice is no longer valid.")

        # Check request is unchanged
        request = input_manager.get_active_request(chat_id)
        assert request.response is None


class TestAskUserChoice:
    @pytest.mark.asyncio
    async def test_list_choices(self, mock_deps, mock_state):
        # Setup
        chat_id = 789
        question = "Test question"
        choices = ["option1", "option2", "option3"]

        # Call function
        await ask_user_choice(
            chat_id=chat_id,
            question=question,
            choices=choices,
            state=mock_state,
            timeout=0.1,
        )

        # Verify keyboard was created correctly
        call_kwargs = mock_deps.bot.send_message.call_args[1]
        assert "reply_markup" in call_kwargs
        assert isinstance(call_kwargs["reply_markup"], InlineKeyboardMarkup)

        # Check first option is marked as default
        keyboard = call_kwargs["reply_markup"].inline_keyboard
        assert len(keyboard) == len(choices)
        assert "⭐" in keyboard[0][0].text
