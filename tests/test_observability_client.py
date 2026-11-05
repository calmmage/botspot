"""Persistence, security and lifecycle tests without external Mongo or Telegram."""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Chat, Message, Update, User
from loguru import logger

from botspot.components.new.observability import Observability, ObservabilitySettings
from botspot.core.bot_manager import BotManager
from botspot.observability.client import (
    ObservabilityClient,
    log_sink,
    record_event,
    record_usage,
    redact,
    request_context,
)
from tests.telegram import TEST_TOKEN, MemoryCollection, MemoryDatabase


class IndexedDatabase(MemoryDatabase):
    def get_collection(self, name):
        if name not in self._cols:
            collection = MemoryCollection(name)
            collection.create_index = AsyncMock()
            self._cols[name] = collection
        return self._cols[name]


@pytest.mark.asyncio
async def test_standalone_events_usage_and_correlated_redacted_sink():
    database = IndexedDatabase()
    client = ObservabilityClient(database, "save_as", secrets=("known-secret-value",))
    context = request_context.set({"request_id": "request-1", "user_id": 42, "chat_id": 43})
    sink = logger.add(client.sink, level="DEBUG", loop=asyncio.get_running_loop())
    try:
        logger.debug("do not persist")
        logger.info("token={} https://cdn.test/file?X-Amz-Signature=abc", TEST_TOKEN)
        try:
            raise ValueError("known-secret-value")
        except ValueError:
            logger.exception("download failed")
        await record_event(client, outcome="ok", kind="message")
        await record_usage(client, "download", cost=0.25, api_key="private")
        await logger.complete()
    finally:
        logger.remove(sink)
        request_context.reset(context)
    logs = database["botspot_logs"].docs
    assert len(logs) == 2
    assert logs[0]["request_id"] == "request-1"
    assert logs[0]["user_id"] == 42
    assert TEST_TOKEN not in str(logs)
    assert "X-Amz-Signature" not in str(logs)
    assert "known-secret-value" not in str(logs)
    assert "ValueError" in logs[1]["exception"]
    event = database["botspot_events"].docs[0]
    assert event["bot"] == "save_as"
    assert event["started_at"] <= event["finished_at"]
    assert event["latency_ms"] >= 0
    usage = database["botspot_usage"].docs[0]
    assert usage["cost"] == 0.25 and usage["api_key"] == "[REDACTED]"
    assert usage["request_id"] == "request-1"


def test_redaction_nested_secrets_urls_and_assignment():
    doc = redact(
        {
            "nested": {"Authorization": "Bearer private"},
            "lines": [
                "password=abc API_KEY: secretvalue",
                "mongodb://user:pass@host/db",
                "https://cdn.test/file?token=abc&signature=def#fragment",
            ],
        }
    )
    assert "private" not in str(doc)
    assert "secretvalue" not in str(doc)
    assert "user:pass" not in str(doc)
    assert "signature=def" not in str(doc)
    assert doc["lines"][1] == "mongodb://host/db"


@pytest.mark.asyncio
async def test_ttl_and_filter_indexes_created_on_both_databases():
    db, registry = IndexedDatabase(), IndexedDatabase()
    client = ObservabilityClient(db, "bot", registry_database=registry)
    await client.ensure_indexes(30)
    for name in ("logs", "events", "errors", "usage"):
        calls = db[f"botspot_{name}"].create_index.call_args_list
        ttl_calls = [c for c in calls if "expireAfterSeconds" in c.kwargs]
        if name == "logs":
            assert ttl_calls[0].args == ("time",)
            assert ttl_calls[0].kwargs["expireAfterSeconds"] == 2592000
        else:
            assert not ttl_calls
        assert any(c.args == ([("bot", 1), ("request_id", 1), ("time", -1)],) for c in calls)
    registry["botspot_bot_registry"].create_index.assert_any_await("bot_id", unique=True)
    registry["botspot_bot_registry"].create_index.assert_any_await("owners")


@pytest.mark.asyncio
async def test_storage_outage_does_not_replace_application_outcome(capsys):
    db = IndexedDatabase()
    db["botspot_events"].insert_one = AsyncMock(side_effect=ConnectionError("mongodb://secret"))
    client = ObservabilityClient(db, "bot")
    await client.record_event(outcome="ok")
    assert client.failed_writes == 1
    assert "ConnectionError" in capsys.readouterr().err


@pytest.mark.asyncio
async def test_standalone_url_factory_without_dispatcher(monkeypatch):
    import pymongo

    class Mongo:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.close = AsyncMock()
            self.database = IndexedDatabase()

        def __getitem__(self, name):
            return self.database

    monkeypatch.setattr(pymongo, "AsyncMongoClient", Mongo)
    sink = log_sink("mongodb://unused", "kurigram")
    client = sink.__self__
    await client.record_usage("download", file_kind="video")
    assert client.database["botspot_usage"].docs[0]["kind"] == "download"
    await client.close()
    client._mongo_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_component_startup_shutdown_mount_and_registry(monkeypatch):
    db = IndexedDatabase()
    bot = SimpleNamespace(
        id=123,
        token=TEST_TOKEN,
        get_me=AsyncMock(return_value=SimpleNamespace(id=123, username="test_bot")),
    )
    component = Observability(
        ObservabilitySettings(public_url="https://bot.test"), db, bot, ["42", "@Owner"]
    )
    from aiohttp import web

    app = web.Application()
    component.mount(app)
    assert len(list(app.router.routes())) > 5
    registration = AsyncMock()
    monkeypatch.setattr("botspot.components.new.observability.register_owner_menu", registration)
    await component.startup()
    assert component._runner is None
    registration.assert_awaited_once_with(bot, ["42", "@Owner"], "https://bot.test")
    registry = db["botspot_bot_registry"].docs[0]
    assert registry["owners"] == ["id:42", "username:owner"]
    assert registry["dashboard_url"] == "https://bot.test/botspot/dashboard"
    first = registry["last_heartbeat"]
    await component.heartbeat()
    assert len(db["botspot_bot_registry"].docs) == 1
    assert db["botspot_bot_registry"].docs[0]["last_heartbeat"] >= first
    await component._register_identity({"id": 43, "username": "Owner"})
    assert registration.await_count == 2
    await component._register_identity({"id": 43, "username": "Owner"})
    assert registration.await_count == 2
    await component._register_identity({"id": 666, "username": "outsider"})
    assert registration.await_count == 2
    await component.shutdown()
    assert component._heartbeat_task.cancelled()


@pytest.mark.asyncio
async def test_owner_commands_precede_app_catchall_and_block_nonowners():
    bot = Bot(TEST_TOKEN)
    bot.__dict__["answer"] = AsyncMock()
    dp, router = Dispatcher(), Router()
    catchall = AsyncMock()

    async def fallback(message):
        await catchall(message)

    router.message.register(fallback)
    dp.include_router(router)
    component = Observability(
        ObservabilitySettings(public_url="https://bot.test"), IndexedDatabase(), bot, ["42"]
    )
    component._register_identity = AsyncMock()
    component.setup_dispatcher(dp)
    from aiogram.methods import SendMessage

    calls = []

    async def mocked(bot_instance, method, **kwargs):
        calls.append(method)
        return True

    bot.session.make_request = mocked

    def update(user_id):
        return Update(
            update_id=user_id,
            message=Message(
                message_id=1,
                date=datetime.now(UTC),
                from_user=User(id=user_id, is_bot=False, first_name="Test"),
                chat=Chat(id=user_id, type="private"),
                text="/logs",
            ),
        )

    await dp.feed_update(bot, update(42))
    assert len(calls) == 1 and isinstance(calls[0], SendMessage)
    assert (
        calls[0].reply_markup.inline_keyboard[0][0].web_app.url == "https://bot.test/botspot/logs"
    )
    await dp.feed_update(bot, update(66))
    assert len(calls) == 1 and catchall.await_count == 1
    await bot.session.close()


def test_default_enabled_and_existing_admin_env_alias(monkeypatch):
    from botspot.core.botspot_settings import BotspotSettings

    monkeypatch.setenv("BOTSPOT_ADMINS", "42,@Owner")
    settings = BotspotSettings()
    assert settings.observability.enabled
    assert settings.admins == ["42", "@Owner"]
    manager = BotManager(observability={"enabled": False})
    assert manager.deps.observability is None


@pytest.mark.asyncio
async def test_menu_and_registry_outages_leave_startup_updates_and_cleanup_usable(
    monkeypatch, capsys
):
    from aiohttp import web

    db = IndexedDatabase()
    registry = db["botspot_bot_registry"]
    registry.update_one = AsyncMock(side_effect=ConnectionError("unavailable"))
    bot = SimpleNamespace(
        id=123,
        token=TEST_TOKEN,
        get_me=AsyncMock(return_value=SimpleNamespace(id=123, username="test_bot")),
    )
    component = Observability(ObservabilitySettings(public_url="https://bot.test"), db, bot, ["42"])
    component.mount(web.Application())
    monkeypatch.setattr(
        "botspot.components.new.observability.register_owner_menu",
        AsyncMock(side_effect=ConnectionError("no private chat yet")),
    )
    await component.startup()
    await component._register_identity({"id": 42})
    assert 42 not in component._registered
    assert not component._heartbeat_task.done()
    registry.update_one = AsyncMock()
    await component.heartbeat()
    registry.update_one.assert_awaited_once()
    await component.shutdown()
    assert "ConnectionError" in capsys.readouterr().err
    assert component._heartbeat_task.cancelled()


def test_bot_manager_wires_default_observability_to_existing_database(monkeypatch):
    from botspot.components.data import mongo_database

    database = IndexedDatabase()
    mongo = SimpleNamespace()
    monkeypatch.setattr(mongo_database, "initialize", lambda settings: (mongo, database))
    bot = Bot(TEST_TOKEN)
    manager = BotManager(bot=bot, mongo_database={"enabled": True})
    assert manager.settings.observability.enabled
    assert manager.deps.observability.client.database is database
    dp = Dispatcher()
    manager.setup_dispatcher(dp)
    assert any(
        handler.callback == manager.deps.observability.startup for handler in dp.startup.handlers
    )
    assert dp.sub_routers[0].name == "botspot_observability"
