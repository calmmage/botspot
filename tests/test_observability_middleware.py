"""Real aiogram routing verifies request outcomes without Telegram network calls."""

import asyncio
import importlib
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Chat, Message, Update, User
from loguru import logger

from botspot.components.middlewares import error_handler
from botspot.components.new.observability.middleware import setup_dispatcher
from botspot.observability.client import request_context

TOKEN = "123456789:AATestingTokenForBotspotNotReal"


def _message(text="hello", update_id=1, user_id=42):
    return Update(
        update_id=update_id,
        message=Message(
            message_id=update_id,
            date=datetime.now(UTC),
            chat=Chat(id=user_id, type="private"),
            from_user=User(id=user_id, is_bot=False, first_name="Test", username="owner"),
            text=text,
        ),
    )


def _client():
    return SimpleNamespace(record_event=AsyncMock(), record_error=AsyncMock())


@pytest.mark.asyncio
async def test_ok_ignored_and_child_router_handler_names():
    client, dp, router = _client(), Dispatcher(), Router()
    setup_dispatcher(dp, client)

    @router.message(Command("ok"))
    async def handle_message(message):
        assert request_context.get()["user_id"] == message.from_user.id

    dp.include_router(router)
    bot = Bot(TOKEN)
    await dp.feed_update(bot, _message("/ok"))
    await dp.feed_update(bot, _message("unhandled", update_id=2))
    rows = [call.kwargs for call in client.record_event.await_args_list]
    assert len(rows) == 2
    assert [row["outcome"] for row in rows] == ["ok", "ignored"]
    ok, ignored = rows
    assert ok["handler"].endswith(".handle_message")
    assert ignored["handler"] is None
    assert ok["kind"] == "message"
    assert (ok["user_id"], ok["chat_id"]) == (42, 42)
    assert ok["finished_at"] >= ok["started_at"]
    assert ok["latency_ms"] >= 0
    assert ok["request_id"] != ignored["request_id"]
    assert request_context.get() == {}
    await bot.session.close()


@pytest.mark.asyncio
async def test_exception_is_archived_before_global_error_handler():
    client, dp = _client(), Dispatcher()
    setup_dispatcher(dp, client)
    seen = []

    @dp.message()
    async def broken(message):
        raise ValueError("failed product request")

    @dp.errors()
    async def global_error(event, observability_context):
        seen.append(observability_context)
        assert client.record_error.await_count == 1
        return True

    bot = Bot(TOKEN)
    assert await dp.feed_update(bot, _message()) is True
    row = client.record_event.await_args.kwargs
    error = client.record_error.await_args.kwargs
    assert row["outcome"] == "error"
    assert row["error_type"] == "ValueError"
    assert error["request_id"] == row["request_id"] == seen[0]["request_id"]
    assert error["error_message"] == "failed product request"
    assert "raise ValueError" in error["traceback"]
    await bot.session.close()


@pytest.mark.asyncio
async def test_disabled_global_error_handler_still_archives_and_reraises():
    client, dp = _client(), Dispatcher()
    setup_dispatcher(dp, client)

    @dp.message()
    async def broken(message):
        raise RuntimeError("no alert handler")

    bot = Bot(TOKEN)
    with pytest.raises(RuntimeError, match="no alert handler"):
        await dp.feed_update(bot, _message())
    assert client.record_error.await_count == 1
    assert client.record_event.await_args.kwargs["outcome"] == "error"
    assert request_context.get() == {}
    await bot.session.close()


@pytest.mark.asyncio
async def test_callback_query_captures_user_and_message_chat():
    client, dp = _client(), Dispatcher()
    setup_dispatcher(dp, client)

    @dp.callback_query()
    async def clicked(callback):
        return True

    message = _message().message
    callback = CallbackQuery(
        id="test",
        from_user=message.from_user,
        message=message,
        chat_instance="test",
        data="clicked",
    )
    bot = Bot(TOKEN)
    await dp.feed_update(bot, Update(update_id=2, callback_query=callback))
    row = client.record_event.await_args.kwargs
    assert row["kind"] == "callback_query"
    assert (row["user_id"], row["chat_id"]) == (42, 42)
    assert row["handler"].endswith(".clicked")
    await bot.session.close()


@pytest.mark.asyncio
async def test_concurrent_updates_keep_log_context_isolated():
    client, dp = _client(), Dispatcher()
    setup_dispatcher(dp, client)
    records = []
    sink = logger.add(lambda msg: records.append(msg.record), level="INFO")

    @dp.message()
    async def handle(message):
        await asyncio.sleep(0)
        logger.info("handled {}", message.from_user.id)

    bot = Bot(TOKEN)
    try:
        await asyncio.gather(
            dp.feed_update(bot, _message(user_id=42)),
            dp.feed_update(bot, _message(update_id=2, user_id=43)),
        )
    finally:
        logger.remove(sink)
        await bot.session.close()
    rows = {r.kwargs["user_id"]: r.kwargs for r in client.record_event.await_args_list}
    handled = [r for r in records if r["message"].startswith("handled ")]
    assert len(handled) == 2
    for record in handled:
        user_id = record["extra"]["user_id"]
        assert record["extra"]["request_id"] == rows[user_id]["request_id"]
    assert rows[42]["request_id"] != rows[43]["request_id"]


@pytest.mark.asyncio
async def test_existing_error_handler_archives_and_preserves_alerts(monkeypatch):
    client = _client()
    deps = SimpleNamespace(
        observability=client,
        botspot_settings=SimpleNamespace(
            error_handling=SimpleNamespace(easter_eggs=False, developer_chat_id=999),
        ),
    )
    monkeypatch.setattr("botspot.core.dependency_manager.get_dependency_manager", lambda: deps)
    answer, send = AsyncMock(), AsyncMock()
    send_module = importlib.import_module("botspot.utils.send_safe")
    monkeypatch.setattr(send_module, "answer_safe", answer)
    monkeypatch.setattr(send_module, "send_safe", send)
    update = _message()
    context = {"request_id": "same-request", "user_id": 42, "chat_id": 42}
    from aiogram.types import ErrorEvent

    await error_handler.error_handler(
        ErrorEvent(update=update, exception=ValueError("failure")),
        Bot(TOKEN),
        context,
    )
    assert client.record_error.await_args.kwargs["request_id"] == "same-request"
    assert client.record_error.await_args.kwargs["error_type"] == "ValueError"
    assert answer.await_count == 1
    assert send.await_args.kwargs["chat_id"] == 999
    assert "failure" in send.await_args.kwargs["text"]


@pytest.mark.asyncio
async def test_real_client_upserts_one_error_and_correlates_global_error_log(monkeypatch):
    from botspot.observability.client import ObservabilityClient
    from tests.telegram import MemoryDatabase

    database = MemoryDatabase()
    client, dp = ObservabilityClient(database, "test_bot"), Dispatcher()
    setup_dispatcher(dp, client)
    deps = SimpleNamespace(
        observability=client,
        botspot_settings=SimpleNamespace(
            error_handling=SimpleNamespace(easter_eggs=False, developer_chat_id=999),
        ),
    )
    monkeypatch.setattr("botspot.core.dependency_manager.get_dependency_manager", lambda: deps)
    send_module = importlib.import_module("botspot.utils.send_safe")
    monkeypatch.setattr(send_module, "answer_safe", AsyncMock())
    monkeypatch.setattr(send_module, "send_safe", AsyncMock())
    records = []
    sink = logger.add(lambda message: records.append(message.record), level="ERROR")

    @dp.message()
    async def broken(message):
        raise RuntimeError("one failure")

    dp.errors.register(error_handler.error_handler)
    bot = Bot(TOKEN)
    try:
        await dp.feed_update(bot, _message())
    finally:
        logger.remove(sink)
        await bot.session.close()
    assert len(database["botspot_errors"].docs) == 1
    assert len(database["botspot_events"].docs) == 1
    error = database["botspot_errors"].docs[0]
    event = database["botspot_events"].docs[0]
    assert error["request_id"] == event["request_id"]
    assert error["error_type"] == "RuntimeError"
    assert "raise RuntimeError" in error["traceback"]
    assert records[0]["extra"]["request_id"] == event["request_id"]
