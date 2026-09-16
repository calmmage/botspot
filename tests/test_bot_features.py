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


@pytest.mark.asyncio
async def test_single_user_mode_blocks_strangers_and_allows_owner():
    router = _router()

    @router.message(Command("ping"))
    async def ping(message: Message):
        await message.answer("pong")

    client = BotClient(router, single_user_mode={"enabled": True, "user": "owner"})
    blocked = await client.send("/ping", username="pleb")
    assert any("personal bot" in t for t in client.texts(blocked))
    assert not any("pong" in t for t in client.texts(blocked))

    allowed = await client.send("/ping", username="owner", user_id=42)
    assert any("pong" in t for t in client.texts(allowed))


@pytest.mark.asyncio
async def test_trial_mode_isolates_users_and_enforces_a_global_cap():
    router = _router()

    @router.message(Command("ping"))
    async def ping(message: Message):
        await message.answer("pong")

    per_user = BotClient(
        router,
        trial_mode={"enabled": True, "limit_per_user": 1, "period_per_user": 3600},
    )
    assert any("pong" in t for t in per_user.texts(await per_user.send("/ping", user_id=1)))
    assert "pong" not in "\n".join(per_user.texts(await per_user.send("/ping", user_id=1)))
    assert any(
        "pong" in t for t in per_user.texts(await per_user.send("/ping", user_id=2, username="b"))
    )

    global_router = _router()

    @global_router.message(Command("ping"))
    async def ping_global(message: Message):
        await message.answer("pong")

    capped = BotClient(
        global_router,
        trial_mode={
            "enabled": True,
            "limit_per_user": 99,
            "global_limit": 1,
            "global_period": 3600,
        },
    )
    assert any("pong" in t for t in capped.texts(await capped.send("/ping", user_id=1)))
    second = "\n".join(capped.texts(await capped.send("/ping", user_id=2, username="b")))
    assert "pong" not in second
    assert "global usage limit" in second


@pytest.mark.asyncio
async def test_error_handler_uses_the_users_language():
    router = _router()

    @router.message(Command("boom"))
    async def boom(_message: Message):
        raise RuntimeError("kaboom")

    client = BotClient(router, error_handling={"enabled": True, "easter_eggs": False})
    out = await client.send("/boom", language_code="ru")
    assert any("Упс, что-то пошло не так" in t for t in client.texts(out))


@pytest.mark.asyncio
async def test_hidden_commands_are_listed_but_not_published_to_telegram():
    from botspot.commands_menu import Visibility

    router = _router()

    @botspot_command("secret", "A hidden ping", visibility=Visibility.HIDDEN)
    @router.message(Command("secret"))
    async def secret(message: Message):
        await message.answer("shh")

    @botspot_command("nuke", "Admin only", visibility=Visibility.ADMIN_ONLY)
    @router.message(Command("nuke"))
    async def nuke(message: Message):
        await message.answer("boom")

    client = BotClient(router, admins_str="@admin")
    startup = await client.emit_startup()
    set_cmds = [m for m in startup if m.__api_method__ == "setMyCommands"]
    names = {c.command for c in set_cmds[0].commands}
    assert "secret" not in names
    assert "nuke" not in names
    assert "list_commands" in names

    listed = "\n".join(client.texts(await client.send("/list_commands", username="pleb")))
    assert "/secret" in listed
    assert "/nuke" not in listed

    admin_listed = "\n".join(
        client.texts(await client.send("/list_commands", username="admin", user_id=42))
    )
    assert "/nuke" in admin_listed


@pytest.mark.asyncio
async def test_callback_query_reaches_a_handler():
    from aiogram.types import CallbackQuery

    router = _router()

    @router.callback_query()
    async def on_click(query: CallbackQuery):
        await query.answer()
        assert query.message is not None
        await query.message.answer(f"clicked {query.data}")

    client = BotClient(router)
    out = await client.callback("pick:1")
    assert any(m.__api_method__ == "answerCallbackQuery" for m in out)
    assert any("clicked pick:1" in t for t in client.texts(out))


@pytest.mark.asyncio
async def test_postgres_disposes_on_shutdown(tmp_path: Path):
    db = tmp_path / "bot.db"
    client = BotClient(postgres_database={"enabled": True, "url": f"sqlite+aiosqlite:///{db}"})
    assert client.manager.deps.postgres_engine is not None
    await client.emit_shutdown()
    assert client.manager.deps._postgres_engine is None


@pytest.mark.asyncio
async def test_simple_user_cache_indexes_first_and_last_name():
    client = BotClient()
    await client.send("hi", first_name="Ada", last_name="Lovelace")
    cache = get_simple_user_cache()
    cached = cache.get_user(1001)
    assert cached is not None
    assert cached.first_name == "Ada"
    assert cached.last_name == "Lovelace"
    assert cache.find_user("Ada Lovelace")
    assert cache.get_user_by_username("tester") is cached


@pytest.mark.asyncio
async def test_send_typing_status_calls_telegram():
    from botspot.utils.unsorted import send_typing_status
    from tests.telegram import make_message

    client = BotClient()
    await send_typing_status(make_message("hi", chat_id=42))
    actions = client.session.by_method("sendChatAction")
    assert actions
    assert actions[0].chat_id == 42
