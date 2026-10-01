"""Minimal chatgpt_plan demo. Needs an OpenAI-issued client ID; the host app must also
serve ``chatgpt_plan.aiohttp_routes(...)`` at the redirect URI."""

from aiogram import F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from botspot.commands_menu import botspot_command
from botspot.components.new import chatgpt_plan
from botspot.utils import send_safe
from examples.base_bot import App, main, router


class ChatgptPlanDemoApp(App):
    name = "ChatGPT Plan Demo"


@botspot_command("link_chatgpt", "Use your ChatGPT plan")
@router.message(Command("link_chatgpt"))
async def link_handler(message: Message):
    url = await chatgpt_plan.start_link(message.from_user.id)
    button = InlineKeyboardButton(text="Sign in with ChatGPT", url=url)
    markup = InlineKeyboardMarkup(inline_keyboard=[[button]])
    await message.answer("Link your ChatGPT plan:", reply_markup=markup)


@router.message(F.text)
async def chat_handler(message: Message):
    answer = await chatgpt_plan.respond(message.from_user.id, "gpt-6-astra", message.text)
    await send_safe(message.chat.id, answer.text)


if __name__ == "__main__":
    main(routers=[router], AppClass=ChatgptPlanDemoApp)
