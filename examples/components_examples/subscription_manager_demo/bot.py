"""Minimal subscription_manager demo. Enable MongoDB + the component in .env."""

from aiogram.filters import Command
from aiogram.types import Message

from botspot.commands_menu import botspot_command
from botspot.components.new.subscription_manager import get_subscription_manager, require_plan
from botspot.utils import send_safe
from examples.base_bot import App, main, router


class SubscriptionDemoApp(App):
    name = "Subscription Demo"


@botspot_command("start", "Start")
@router.message(Command("start"))
async def start_handler(message: Message):
    await send_safe(
        message.chat.id,
        "Plans: /subscribe /plans /account /buy\nPaid-only: /plus_feature",
    )


@botspot_command("plus_feature", "Requires a paid plan")
@router.message(Command("plus_feature"))
@require_plan()
async def plus_feature(message: Message):
    ent = await get_subscription_manager().check_entitlement(message.from_user.id)
    await send_safe(message.chat.id, f"ok source={ent.source} plan={ent.plan_id}")


if __name__ == "__main__":
    main(routers=[router], AppClass=SubscriptionDemoApp)
