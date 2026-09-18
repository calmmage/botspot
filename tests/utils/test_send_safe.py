"""send_safe against a real Bot + mocked Telegram session."""

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile

from botspot.utils.send_safe import answer_safe, reply_safe, send_safe
from botspot.utils.text_utils import MAX_TELEGRAM_MESSAGE_LENGTH
from tests.telegram import DEFAULT_CHAT_ID, BotClient, make_message


@pytest.mark.asyncio
async def test_basic_send():
    client = BotClient()
    await send_safe(DEFAULT_CHAT_ID, "hello world")
    sent = client.session.by_method("sendMessage")
    assert len(sent) == 1
    assert sent[0].text == "hello world"
    assert sent[0].chat_id == DEFAULT_CHAT_ID


@pytest.mark.asyncio
async def test_wrap_text():
    client = BotClient(send_safe={"enabled": True, "wrap_text": True, "wrap_width": 20})
    text = "A very long line that should be wrapped according to settings"
    await send_safe(DEFAULT_CHAT_ID, text)
    sent_text = client.session.by_method("sendMessage")[0].text
    assert max(len(line) for line in sent_text.split("\n")) <= 20


@pytest.mark.asyncio
async def test_long_message_as_file():
    client = BotClient(send_safe={"enabled": True, "send_long_messages_as_files": True})
    await send_safe(DEFAULT_CHAT_ID, "A" * (MAX_TELEGRAM_MESSAGE_LENGTH + 50))
    docs = client.session.by_method("sendDocument")
    assert docs
    document = docs[0].document
    assert isinstance(document, BufferedInputFile)
    assert document.filename is not None and document.filename.endswith(".txt")


@pytest.mark.asyncio
async def test_long_message_split():
    client = BotClient(send_safe={"enabled": True, "send_long_messages_as_files": False})
    await send_safe(DEFAULT_CHAT_ID, "A" * (MAX_TELEGRAM_MESSAGE_LENGTH + 50))
    assert len(client.session.by_method("sendMessage")) > 1


@pytest.mark.asyncio
async def test_message_as_chat_id():
    client = BotClient()
    message = make_message("incoming", chat_id=42, message_id=7)
    await send_safe(message, "reply-ish")
    sent = client.session.by_method("sendMessage")[0]
    assert sent.chat_id == 42
    assert sent.reply_to_message_id == 7


@pytest.mark.asyncio
async def test_reply_and_answer_safe():
    client = BotClient()
    message = make_message("incoming", chat_id=42, message_id=7)
    await reply_safe(message, "replied")
    await answer_safe(message, "answered")
    texts = client.session.texts()
    assert "replied" in texts
    assert "answered" in texts


@pytest.mark.asyncio
async def test_auto_delete_issues_delete_message():
    import asyncio

    client = BotClient()
    await send_safe(DEFAULT_CHAT_ID, "ephemeral", cleanup=True, cleanup_timeout=0)
    await asyncio.sleep(0.05)
    assert client.session.by_method("deleteMessage")


@pytest.mark.asyncio
async def test_long_message_preview_then_file():
    client = BotClient(
        send_safe={
            "enabled": True,
            "send_long_messages_as_files": True,
            "send_preview_for_long_messages": True,
            "preview_cutoff": 20,
        }
    )
    await send_safe(DEFAULT_CHAT_ID, "A" * (MAX_TELEGRAM_MESSAGE_LENGTH + 50))
    assert client.session.by_method("sendDocument")
    preview = [t for t in client.texts() if "Preview" in t or "too long" in t]
    assert preview


@pytest.mark.asyncio
async def test_parse_mode_fallback():
    client = BotClient()
    calls = {"n": 0}
    original = client.session.make_request

    async def flaky(bot, method, timeout=None):
        if method.__api_method__ == "sendMessage":
            calls["n"] += 1
            if calls["n"] == 1:
                client.session.requests.append(method)
                raise TelegramBadRequest(method=method, message="can't parse entities")
        return await original(bot, method, timeout)

    client.session.make_request = flaky  # type: ignore[method-assign]
    await send_safe(DEFAULT_CHAT_ID, "<b>broken", parse_mode="HTML")
    assert calls["n"] == 2
    assert client.session.by_method("sendMessage")[-1].text == "<b>broken"
