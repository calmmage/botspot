"""Outgoing emoji come from one custom pack.

Copy example.env to .env, then run this file.
pack=random picks a catalog pack per message.
pack=StaticEmoji (or CuteEmoji,StaticEmoji) pins the choice.
BOTSPOT_TELEGRAM_CUSTOM_EMOJIS_ENABLED=false sends the unicode emoji.
"""

from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from botspot.commands_menu import botspot_command
from examples.base_bot import App, main, router


class CustomEmojiDemoApp(App):
    name = "Custom Emoji Demo"


@botspot_command("start", "Start")
@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        "📅 История мероприятий\n✅ Пермь — 75 чел.\n⏰ Ждём вас",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🎟 Билет", callback_data="ticket")]]
        ),
    )


if __name__ == "__main__":
    main(routers=[router], AppClass=CustomEmojiDemoApp)
