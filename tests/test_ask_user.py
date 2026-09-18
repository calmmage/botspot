"""ask_user / ask_user_choice / ask_user_confirmation through the real dispatcher."""

import asyncio

import pytest
from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from botspot.components.features.user_interactions import (
    ask_user,
    ask_user_choice,
    ask_user_confirmation,
    input_manager,
)
from tests.telegram import DEFAULT_CHAT_ID, BotClient


@pytest.fixture(autouse=True)
def _clear_input_manager():
    input_manager._pending_requests = {}
    yield
    input_manager._pending_requests = {}


def _router() -> Router:
    return Router()


@pytest.mark.asyncio
async def test_ask_user_collects_the_next_text_reply():
    router = _router()

    @router.message(Command("ask"))
    async def ask(message: Message, state: FSMContext):
        answer = await ask_user(message.chat.id, "What is your name?", state, timeout=2)
        await message.answer(f"got {answer}")

    client = BotClient(router, ask_user={"enabled": True})
    ask_task = asyncio.create_task(client.send("/ask"))
    for _ in range(50):
        if any("What is your name?" in t for t in client.texts()):
            break
        await asyncio.sleep(0.02)
    else:
        raise AssertionError("bot never asked the question")

    await client.send("Alice")
    await ask_task
    assert any("got Alice" in t for t in client.texts())


@pytest.mark.asyncio
async def test_ask_user_times_out_without_a_reply():
    router = _router()

    @router.message(Command("ask"))
    async def ask(message: Message, state: FSMContext):
        answer = await ask_user(message.chat.id, "Name?", state, timeout=0.05)
        await message.answer("none" if answer is None else answer)

    client = BotClient(router, ask_user={"enabled": True})
    await client.send("/ask")
    texts = client.texts()
    assert any(t == "none" or "none" in t for t in texts)
    edited = client.session.by_method("editMessageText")
    assert edited
    assert any("time limit" in (m.text or "") or "No response" in (m.text or "") for m in edited)


@pytest.mark.asyncio
async def test_ask_user_choice_via_inline_button():
    router = _router()

    @router.message(Command("choose"))
    async def choose(message: Message, state: FSMContext):
        pick = await ask_user_choice(message.chat.id, "Pick one", ["red", "blue"], state, timeout=2)
        await message.answer(f"picked {pick}")

    client = BotClient(router, ask_user={"enabled": True})
    choose_task = asyncio.create_task(client.send("/choose"))
    question = None
    for _ in range(50):
        sent = client.session.by_method("sendMessage")
        if sent and getattr(sent[-1], "reply_markup", None):
            question = sent[-1]
            break
        await asyncio.sleep(0.02)
    assert question is not None
    keyboard = question.reply_markup.inline_keyboard
    assert any("⭐" in btn.text for row in keyboard for btn in row)

    await client.callback(
        "choice_blue",
        message_id=question.message_id if hasattr(question, "message_id") else 1,
        message_text="Pick one",
        chat_id=DEFAULT_CHAT_ID,
    )
    await choose_task
    assert any("picked blue" in t for t in client.texts())


@pytest.mark.asyncio
async def test_ask_user_confirmation_yes_via_callback():
    router = _router()

    @router.message(Command("sure"))
    async def sure(message: Message, state: FSMContext):
        ok = await ask_user_confirmation(message.chat.id, "Are you sure?", state, timeout=2)
        await message.answer("yes" if ok else "no")

    client = BotClient(router, ask_user={"enabled": True})
    task = asyncio.create_task(client.send("/sure"))
    question = None
    for _ in range(50):
        sent = client.session.by_method("sendMessage")
        if sent and getattr(sent[-1], "reply_markup", None):
            question = sent[-1]
            break
        await asyncio.sleep(0.02)
    assert question is not None
    await client.callback("choice_yes", message_text="Are you sure?")
    await task
    assert any(t == "yes" for t in client.texts())
