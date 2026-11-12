"""Custom Telegram emoji: pack choice and outgoing rewrite."""

import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.methods import SendMessage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from botspot.components.qol.telegram_custom_emojis import (
    TelegramCustomEmojis,
    TelegramCustomEmojisSettings,
)
from botspot.core.bot_manager import BotManager
from tests.telegram import TEST_TOKEN, BotClient


def _component(**kwargs) -> TelegramCustomEmojis:
    defaults = {"enabled": True, "pack": "StaticEmoji"}
    defaults.update(kwargs)
    return TelegramCustomEmojis(TelegramCustomEmojisSettings(**defaults))


def _html_bot() -> Bot:
    return Bot(
        TEST_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def test_specific_pack_rewrites_message_emoji_and_keeps_plain_dash():
    component = _component()
    bot = _html_bot()
    method = SendMessage(
        chat_id=1,
        text=(
            "📅 История мероприятий:\n\n"
            "— Санкт-Петербург (21 ноября, сб) — 0 чел.\n"
            "✅ Пермь (1 Августа, Сб) — 75 чел.\n"
            "⏰ No response received within the time limit."
        ),
    )
    component.rewrite(method, bot)

    assert "—" in method.text
    assert method.text.count("<tg-emoji ") == 3
    assert 'emoji-id="' in method.text
    for char in ("📅", "✅", "⏰"):
        assert f">{char}</tg-emoji>" in method.text
        assert method.text.count(char) == 1


def test_html_rewrite_is_idempotent_and_skips_code_and_existing_tags():
    component = _component()
    original = '<b>✅ ready</b> <code>✅</code> <tg-emoji emoji-id="1">✅</tg-emoji>'
    once = component.apply_html(original, "StaticEmoji")
    twice = component.apply_html(once, "StaticEmoji")

    assert once == twice
    assert once.count("<tg-emoji ") == 2
    assert "<code>✅</code>" in once
    assert '<tg-emoji emoji-id="1">✅</tg-emoji>' in once
    assert "<b><tg-emoji " in once


def test_plain_text_uses_utf16_custom_emoji_entity():
    component = _component()
    bot = Bot(TEST_TOKEN)
    method = SendMessage(chat_id=1, text="A📅B", parse_mode=None)
    component.rewrite(method, bot)
    component.rewrite(method, bot)

    assert method.text == "A📅B"
    assert len(method.entities) == 1
    entity = method.entities[0]
    assert entity.type == "custom_emoji"
    assert entity.offset == 1
    assert entity.length == 2
    assert entity.custom_emoji_id == component.catalog.packs["StaticEmoji"]["📅"]


def test_button_emoji_becomes_icon_and_label_keeps_the_name():
    component = _component()
    bot = _html_bot()
    method = SendMessage(
        chat_id=1,
        text="Билеты",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🎟 Иван Иванов", callback_data="t")]]
        ),
    )
    component.rewrite(method, bot)
    button = method.reply_markup.inline_keyboard[0][0]

    assert button.text == "Иван Иванов"
    assert button.icon_custom_emoji_id == component.catalog.packs["StaticEmoji"]["🎟"]
    assert button.callback_data == "t"


def test_missing_glyph_stays_unicode_when_the_pack_is_strict():
    component = _component(pack="petrlavrov", allow_other_packs=False)
    assert "✅" not in component.catalog.packs["petrlavrov"]
    assert component.apply_html("✅ Пермь", "petrlavrov") == "✅ Пермь"


def test_other_packs_fill_a_glyph_the_chosen_pack_lacks():
    component = _component(pack="petrlavrov", allow_other_packs=True)
    updated = component.apply_html("✅", "petrlavrov")
    assert updated == f'<tg-emoji emoji-id="{component.catalog.fallback["✅"]}">✅</tg-emoji>'


def test_random_and_list_selection():
    random_component = _component(pack="random")
    seen = {random_component.choose_pack() for _ in range(40)}
    assert len(seen) > 1
    assert seen <= set(random_component.pack_names())

    listed = _component(pack="staticemoji, CuteEmoji")
    assert listed.pack_choices() == ["StaticEmoji", "CuteEmoji"]
    assert _component(pack="not-a-real-pack").pack_choices() == random_component.pack_names()


def test_disabled_component_leaves_text_alone():
    component = _component(enabled=False)
    bot = _html_bot()
    method = SendMessage(chat_id=1, text="✅")
    component.rewrite(method, bot)
    assert method.text == "✅"


def test_expansion_past_the_telegram_limit_keeps_unicode():
    component = _component()
    bot = _html_bot()
    method = SendMessage(chat_id=1, text="✅" * 80, parse_mode="HTML")
    component.rewrite(method, bot)
    assert method.text == "✅" * 80


@pytest.mark.asyncio
async def test_send_safe_message_is_rewritten_on_the_way_out():
    from aiogram import Router
    from aiogram.filters import CommandStart
    from aiogram.types import Message

    from botspot.utils.send_safe import send_safe

    def router() -> Router:
        fresh = Router()

        @fresh.message(CommandStart())
        async def start(message: Message):
            await send_safe(message.chat.id, "📅 История мероприятий\n✅ 75 чел.")

        return fresh

    client = BotClient(
        router(),
        telegram_custom_emojis={"enabled": True, "pack": "StaticEmoji"},
    )
    sent = await client.send("/start")
    texts = [getattr(method, "text", "") for method in sent]
    body = next(text for text in texts if "История" in text)
    assert body.count("<tg-emoji ") == 2
    assert "📅" in body and "✅" in body

    assert isinstance(client.manager, BotManager)
    again = BotClient(router())
    plain = await again.send("/start")
    plain_body = next(
        getattr(method, "text", "") for method in plain if "История" in getattr(method, "text", "")
    )
    assert "<tg-emoji " not in plain_body
