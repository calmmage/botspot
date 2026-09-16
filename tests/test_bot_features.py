"""Dispatcher-level feature tests against a mocked Telegram session."""

from pathlib import Path

import pytest
from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy import text

from botspot.commands_menu import botspot_command
from botspot.components.data.postgres_database import get_session
from botspot.components.new.message_aggregator import get_message_aggregator
from botspot.core.errors import BotspotError
from botspot.utils.admin_filter import AdminFilter
from botspot.utils.deps_getters import get_bot, get_dispatcher, get_simple_user_cache
from botspot.utils.send_safe import send_safe
from tests.telegram import BotClient


def _router() -> Router:
    return Router()


@pytest.mark.asyncio
async def test_start_and_help_go_through_the_dispatcher():
    router = _router()

    @botspot_command("start", "Start the bot")
    @router.message(CommandStart())
    async def start_handler(message: Message):
        assert message.from_user is not None
        await send_safe(message.chat.id, f"Hello, {message.from_user.first_name}!")

    @botspot_command("help", "Show help")
    @router.message(Command("help"))
    async def help_handler(message: Message):
        await send_safe(message.chat.id, "Use /start to begin.")

    client = BotClient(router)
    start_out = await client.send("/start")
    assert any("Hello, Test" in t for t in client.texts(start_out))

    help_out = await client.send("/help")
    assert any("Use /start to begin." in t for t in client.texts(help_out))


@pytest.mark.asyncio
async def test_bot_info_reports_version_and_components():
    import botspot

    client = BotClient()
    out = await client.send("/bot_info")
    joined = "\n".join(client.texts(out))
    assert "🤖 Bot Information" in joined
    assert botspot.__version__ in joined
    assert "Enabled Components:" in joined
    assert "✅ bot_info" in joined
    assert "❌ mongo_database" in joined
    assert "Detailed Settings:" not in joined


@pytest.mark.asyncio
async def test_bot_info_detailed_settings():
    client = BotClient(bot_info={"enabled": True, "show_detailed_settings": True})
    joined = "\n".join(client.texts(await client.send("/bot_info")))
    assert "Detailed Settings:" in joined
    assert '"enabled"' in joined


@pytest.mark.asyncio
async def test_list_commands_and_startup_set_my_commands():
    router = _router()

    @botspot_command("ping", "Ping the bot")
    @router.message(Command("ping"))
    async def ping(message: Message):
        await message.answer("pong")

    client = BotClient(router)
    startup = await client.emit_startup()
    set_cmds = [m for m in startup if m.__api_method__ == "setMyCommands"]
    assert set_cmds, "startup must publish the public command menu"
    published = {c.command for c in set_cmds[0].commands}
    assert "ping" in published
    assert "list_commands" in published
    get_me = [m for m in startup if m.__api_method__ == "getMe"]
    assert get_me, "print_bot_url must call getMe"

    listed = "\n".join(client.texts(await client.send("/list_commands")))
    assert "/ping" in listed
    assert "Ping the bot" in listed


@pytest.mark.asyncio
async def test_error_handler_replies_to_user_and_developer():
    router = _router()

    @router.message(Command("boom"))
    async def boom(_message: Message):
        raise RuntimeError("kaboom")

    client = BotClient(
        router,
        error_handling={"enabled": True, "easter_eggs": False, "developer_chat_id": 999},
    )
    out = await client.send("/boom")
    texts = client.texts(out)
    assert any("Oops, something went wrong" in t for t in texts)
    dev = [m for m in out if getattr(m, "chat_id", None) == 999]
    assert dev, "developer must get the traceback"
    assert "kaboom" in dev[0].text
    assert "Error processing message" in dev[0].text


@pytest.mark.asyncio
async def test_error_handler_sends_botspot_user_message():
    router = _router()

    @router.message(Command("nope"))
    async def nope(_message: Message):
        raise BotspotError("internal", user_message="please try later", report_to_dev=False)

    client = BotClient(
        router,
        error_handling={"enabled": True, "easter_eggs": False, "developer_chat_id": 999},
    )
    out = await client.send("/nope")
    assert any("please try later" in t for t in client.texts(out))
    assert not [m for m in out if getattr(m, "chat_id", None) == 999]


@pytest.mark.asyncio
async def test_admin_filter_blocks_strangers_and_allows_admins():
    router = _router()

    @router.message(Command("secret"), AdminFilter())
    async def secret(message: Message):
        await message.answer("welcome admin")

    client = BotClient(router, admins_str="@admin")
    blocked = await client.send("/secret", username="pleb")
    assert any("You are not an admin" in t for t in client.texts(blocked))
    assert not any("welcome admin" in t for t in client.texts(blocked))

    allowed = await client.send("/secret", username="admin", user_id=42)
    assert any("welcome admin" in t for t in client.texts(allowed))


@pytest.mark.asyncio
async def test_trial_mode_blocks_after_the_per_user_limit():
    router = _router()

    @router.message(Command("ping"))
    async def ping(message: Message):
        await message.answer("pong")

    client = BotClient(
        router,
        trial_mode={"enabled": True, "limit_per_user": 1, "period_per_user": 3600},
    )
    first = await client.send("/ping")
    assert any("pong" in t for t in client.texts(first))
    second = await client.send("/ping")
    joined = "\n".join(client.texts(second))
    assert "pong" not in joined
    assert "personal usage limit" in joined


@pytest.mark.asyncio
async def test_postgres_handler_roundtrips_select_1(tmp_path: Path):
    router = _router()

    @router.message(Command("ping_db"))
    async def ping_db(message: Message):
        async with get_session() as session:
            value = (await session.execute(text("SELECT 1"))).scalar_one()
        await message.answer(f"db ok: {value}")

    db = tmp_path / "bot.db"
    client = BotClient(
        router,
        postgres_database={"enabled": True, "url": f"sqlite+aiosqlite:///{db}"},
    )
    out = await client.send("/ping_db")
    assert any("db ok: 1" in t for t in client.texts(out))


@pytest.mark.asyncio
async def test_message_aggregator_batches_a_burst():
    import asyncio

    router = _router()

    @router.message()
    async def handle(message: Message):
        batch = await get_message_aggregator().collect(message)
        if batch is None:
            return
        await message.answer(f"got {len(batch)}")

    client = BotClient(
        router,
        message_aggregator={"enabled": True, "delay": 0.05, "ignore_commands": False},
    )
    await asyncio.gather(client.send("one"), client.send("two"), client.send("three"))
    texts = client.texts()
    assert any(t == "got 3" for t in texts)


@pytest.mark.asyncio
async def test_getters_return_the_live_bot_and_dispatcher():
    client = BotClient()
    assert get_bot() is client.bot
    assert get_dispatcher() is client.dp
    await client.send("hi")
    cached = get_simple_user_cache().get_user(1001)
    assert cached is not None
    assert cached.username == "tester"



