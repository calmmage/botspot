"""Dispatcher-level tests for Mongo-backed components using MemoryDatabase."""

import asyncio

import pytest
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from botspot.components.new.queue_manager import QueueItem, create_queue, get_queue
from tests.telegram import DEFAULT_CHAT_ID, BotClient


def _router() -> Router:
    return Router()


@pytest.mark.asyncio
async def test_chat_binder_bind_status_list_unbind_roundtrip():
    client = BotClient(
        mongo=True,
        chat_binder={"enabled": True, "commands_visible": True, "check_access": True},
    )
    bound = await client.send("/bind_chat notes")
    assert any("bound successfully" in t and "notes" in t for t in client.texts(bound))

    status = "\n".join(client.texts(await client.send("/bind_status")))
    assert "notes" in status

    listed = "\n".join(client.texts(await client.send("/list_chats")))
    assert "notes" in listed
    assert str(DEFAULT_CHAT_ID) in listed

    got = "\n".join(client.texts(await client.send("/get_chat notes")))
    assert str(DEFAULT_CHAT_ID) in got

    unbound = await client.send("/unbind_chat notes")
    assert any("unbound successfully" in t for t in client.texts(unbound))
    assert any("not bound" in t for t in client.texts(await client.send("/bind_status")))


@pytest.mark.asyncio
async def test_chat_binder_rebind_error_then_replace():
    error_client = BotClient(
        mongo=True,
        chat_binder={
            "enabled": True,
            "commands_visible": True,
            "rebind_mode": "error",
            "check_access": False,
        },
    )
    await error_client.send("/bind_chat")
    again = await error_client.send("/bind_chat")
    # ChatBindingExistsError is not ValueError, so error_handler answers the user
    assert any(
        "something went wrong" in t.lower() or "already bound" in t.lower()
        for t in error_client.texts(again)
    )

    replace_client = BotClient(
        mongo=True,
        chat_binder={
            "enabled": True,
            "commands_visible": True,
            "rebind_mode": "replace",
            "check_access": False,
        },
    )
    await replace_client.send("/bind_chat inbox", chat_id=11)
    await replace_client.send("/bind_chat inbox", chat_id=22)
    got = "\n".join(replace_client.texts(await replace_client.send("/get_chat inbox", chat_id=22)))
    assert "22" in got


@pytest.mark.asyncio
async def test_queue_manager_add_and_pop_from_a_handler():
    router = _router()

    @router.message(Command("push"))
    async def push(message: Message):
        queue = create_queue()
        assert message.text is not None
        await queue.add_item(
            QueueItem(data=message.text.split(maxsplit=1)[1]), user_id=message.from_user.id
        )
        await message.answer("queued")

    @router.message(Command("pop"))
    async def pop(message: Message):
        item = await get_queue().pop(user_id=message.from_user.id)
        await message.answer("empty" if item is None else item.data)

    @router.message(Command("count"))
    async def count(message: Message):
        items = await get_queue().get_items(user_id=message.from_user.id)
        await message.answer(f"n={len(items)}")

    client = BotClient(
        router,
        mongo=True,
        queue_manager={"enabled": True},
    )
    await client.send("/push hello-queue")
    await client.send("/push second")
    assert any("n=2" in t for t in client.texts(await client.send("/count")))
    popped = await client.send("/pop")
    assert any(t in {"hello-queue", "second"} for t in client.texts(popped))
    # pop fetches without deleting
    assert any("n=2" in t for t in client.texts(await client.send("/count")))


@pytest.mark.asyncio
async def test_access_control_list_add_and_remove_friends():
    client = BotClient(
        access_control={"enabled": True},
        admins_str="@admin",
        friends_str="@alice",
    )
    await client.emit_startup()
    listed = "\n".join(
        client.texts(await client.send("/list_friends", username="admin", user_id=42))
    )
    assert "@alice" in listed

    blocked = await client.send("/list_friends", username="pleb")
    assert any("not an admin" in t for t in client.texts(blocked))

    added = await client.send("/add_friend bob", username="admin", user_id=42)
    assert any("bob" in t and "added" in t.lower() for t in client.texts(added))
    listed_again = "\n".join(
        client.texts(await client.send("/list_friends", username="admin", user_id=42))
    )
    assert "@bob" in listed_again

    removed = await client.send("/remove_friend bob", username="admin", user_id=42)
    assert any("removed" in t.lower() for t in client.texts(removed))


@pytest.mark.asyncio
async def test_auto_archive_help_bind_and_skip_tag():
    router = _router()

    @router.message(Command("ping"))
    async def ping(message: Message):
        await message.answer("pong")

    client = BotClient(
        router,
        mongo=True,
        chat_binder={"enabled": True, "commands_visible": True},
        auto_archive={
            "enabled": True,
            "delay": 0,
            "enable_chat_handler": True,
            "bind_command_visible": True,
        },
    )
    unbound = await client.send("remember this")
    assert any("bound chat" in t.lower() for t in client.texts(unbound))

    help_out = await client.send("/help_autoarchive")
    assert any("noarchive" in t.lower() or "auto" in t.lower() for t in client.texts(help_out))

    await client.send("/bind_auto_archive")
    assert any("bound for auto-archiving" in t.lower() for t in client.texts())

    before = len(client.session.requests)
    await client.send("archive me please")
    await asyncio.sleep(0.05)
    new = client.session.requests[before:]
    assert any(m.__api_method__ == "forwardMessage" for m in new)
    assert any(m.__api_method__ == "deleteMessage" for m in new)

    before = len(client.session.requests)
    await client.send("keep #noarchive")
    await asyncio.sleep(0.05)
    tagged = client.session.requests[before:]
    assert not any(m.__api_method__ == "forwardMessage" for m in tagged)
    assert not any(m.__api_method__ == "deleteMessage" for m in tagged)

    before = len(client.session.requests)
    await client.send("group noise", chat_id=-100, chat_type="group")
    await asyncio.sleep(0.05)
    grouped = client.session.requests[before:]
    assert not any(m.__api_method__ == "forwardMessage" for m in grouped)
