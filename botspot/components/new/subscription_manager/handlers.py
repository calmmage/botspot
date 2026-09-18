"""Telegram handlers for /subscribe /account /plans and admin grant/revoke."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from botspot.components.middlewares.i18n import t
from botspot.components.new.subscription_manager.settings import (
    PAID_SOURCES,
    SOURCE_SUBSCRIPTION,
    SUB_ACTIVE,
)
from botspot.utils.admin_filter import AdminFilter
from botspot.utils.internal import get_logger
from botspot.utils.send_safe import send_safe

logger = get_logger()


def get_manager():
    from botspot.components.new.subscription_manager import get_subscription_manager

    return get_subscription_manager()


def require_plan(plan_id: str | None = None):
    """Gate a handler: entitled → run; else reply subscription_required + subscribe keyboard.

    ``require_plan()`` with no arg = any paid entitlement.
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(event: Any, *args, **kwargs):
            user = getattr(event, "from_user", None)
            if user is None:
                return
            manager = get_manager()
            ent = await manager.check_entitlement(int(user.id))
            entitled = ent.source in PAID_SOURCES
            if plan_id and ent.source not in {"admin", "friend"}:
                entitled = entitled and ent.plan_id == plan_id
            if not entitled:
                markup = await subscribe_keyboard(manager)
                text = t("subscription_required")
                if hasattr(event, "answer") and not hasattr(event, "message_id"):
                    await event.answer(text, show_alert=True)
                else:
                    chat_id = event.chat.id if hasattr(event, "chat") else event.message.chat.id
                    await send_safe(chat_id, text, reply_markup=markup)
                return
            return await func(event, *args, **kwargs)

        return wrapper

    return decorator


async def subscribe_keyboard(manager, *, include_packs: bool = True) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for plan in manager.list_plans():
        rows.append(
            [
                InlineKeyboardButton(
                    text=t("subscription_plan_button", title=plan.title, stars=plan.stars),
                    callback_data=f"sub:plan:{plan.plan_id}",
                )
            ]
        )
    if include_packs:
        rows.append(
            [InlineKeyboardButton(text=t("billing_buy_credits"), callback_data="sub:packs")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def packs_keyboard(manager) -> InlineKeyboardMarkup:
    rows = []
    for pack in manager.list_packs():
        rows.append(
            [
                InlineKeyboardButton(
                    text=t("billing_pack_button", usd=int(pack.usd_amount), credits=pack.credits),
                    callback_data=f"sub:pack:{pack.sku}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text=t("billing_back"), callback_data="sub:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def cmd_subscribe(message: Message) -> None:
    manager = get_manager()
    await send_safe(
        message.chat.id,
        t("subscription_picker"),
        reply_markup=await subscribe_keyboard(manager),
    )


async def cmd_plans(message: Message) -> None:
    manager = get_manager()
    lines = [t("subscription_plans_header")]
    for plan in manager.list_plans():
        minutes = f"{plan.minutes_per_period:.0f}" if plan.minutes_per_period else "—"
        lines.append(
            t(
                "subscription_plan_row",
                title=plan.title,
                usd=f"{plan.usd_cents / 100:.2f}",
                stars=plan.stars,
                minutes=minutes,
                seats=plan.seats,
            )
        )
    await send_safe(message.chat.id, "\n".join(lines))


async def cmd_account(message: Message) -> None:
    if message.from_user is None:
        return
    manager = get_manager()
    ent = await manager.check_entitlement(message.from_user.id)
    balance = await manager.get_balance(message.from_user.id)
    until = ent.until.isoformat(sep=" ", timespec="minutes") if ent.until else "—"
    minutes = "∞" if ent.minutes_left is None else f"{ent.minutes_left:.1f}"
    text = t(
        "subscription_account",
        source=ent.source,
        plan=ent.plan_id or "—",
        until=until,
        minutes=minutes,
        credits=balance.balance_credits,
    )
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=t("billing_buy_credits"), callback_data="sub:packs")],
        [InlineKeyboardButton(text=t("subscription_picker_short"), callback_data="sub:home")],
    ]
    if ent.source == SOURCE_SUBSCRIPTION:
        rows.insert(
            0,
            [
                InlineKeyboardButton(
                    text=t("subscription_cancel_renewal"), callback_data="sub:cancel"
                )
            ],
        )
    await send_safe(message.chat.id, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


async def cmd_buy(message: Message) -> None:
    manager = get_manager()
    await send_safe(message.chat.id, t("billing_buy_intro"), reply_markup=packs_keyboard(manager))


async def cmd_grant(message: Message) -> None:
    parts = (message.text or "").split()
    if len(parts) < 3:
        await send_safe(message.chat.id, t("subscription_grant_usage"))
        return
    user_id = int(parts[1])
    plan_id = parts[2]
    days = int(parts[3]) if len(parts) > 3 else None
    granted_by = message.from_user.id if message.from_user else 0
    sub = await get_manager().grant(user_id, plan_id, days=days, granted_by=granted_by)
    await send_safe(
        message.chat.id,
        t("subscription_grant_done", user_id=user_id, plan=sub.plan_id),
    )


async def cmd_revoke(message: Message) -> None:
    parts = (message.text or "").split()
    if len(parts) < 2:
        await send_safe(message.chat.id, t("subscription_revoke_usage"))
        return
    user_id = int(parts[1])
    granted_by = message.from_user.id if message.from_user else 0
    await get_manager().revoke(user_id, granted_by=granted_by)
    await send_safe(message.chat.id, t("subscription_revoke_done", user_id=user_id))


async def cmd_subscribers(message: Message) -> None:
    subs = await get_manager().list_subscribers(status=SUB_ACTIVE)
    if not subs:
        await send_safe(message.chat.id, t("subscription_list_empty"))
        return
    lines = [
        f"{s.user_id} {s.plan_id} {s.provider} until {s.current_period_end.date()}" for s in subs
    ]
    await send_safe(message.chat.id, t("subscription_list_header", entries="\n".join(lines)))


async def cmd_grant_credits(message: Message) -> None:
    parts = (message.text or "").split()
    if len(parts) < 3:
        await send_safe(message.chat.id, t("billing_grant_credits_usage"))
        return
    user_id = int(parts[1])
    credits = int(parts[2])
    granted_by = message.from_user.id if message.from_user else 0
    note = " ".join(parts[3:]) if len(parts) > 3 else ""
    ledger_id = await get_manager().grant_admin_credits(user_id, credits, granted_by, note=note)
    await send_safe(
        message.chat.id,
        t("billing_grant_credits_done", credits=credits, user_id=user_id, ledger_id=ledger_id),
    )


async def on_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.data is None or callback.message is None:
        return
    if not isinstance(callback.message, Message):
        await callback.answer()
        return
    message = callback.message
    data = callback.data
    manager = get_manager()
    user_id = int(callback.from_user.id)
    if data == "sub:home":
        await message.edit_text(
            t("subscription_picker"), reply_markup=await subscribe_keyboard(manager)
        )
        await callback.answer()
        return
    if data == "sub:packs":
        await message.edit_text(t("billing_buy_intro"), reply_markup=packs_keyboard(manager))
        await callback.answer()
        return
    if data == "sub:cancel":
        await manager.cancel_subscription(user_id, at_period_end=True)
        await message.edit_text(t("subscription_cancelled"))
        await callback.answer()
        return
    if data.startswith("sub:plan:"):
        plan_id = data.split(":", 2)[2]
        link = await manager.create_stars_subscription_link(user_id, plan_id)
        plan = manager.get_plan(plan_id)
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=t("subscription_pay_stars", stars=plan.stars), url=link
                    )
                ],
                [InlineKeyboardButton(text=t("billing_buy_credits"), callback_data="sub:packs")],
            ]
        )
        await message.edit_text(
            t("subscription_pay_prompt", title=plan.title, stars=plan.stars),
            reply_markup=markup,
        )
        await callback.answer()
        return
    if data.startswith("sub:pack:"):
        sku = data.split(":", 2)[2]
        invoice = await manager.create_stars_invoice(user_id, sku)
        pack = manager.get_pack(sku)
        bot = manager.bot()
        await bot.send_invoice(
            chat_id=message.chat.id,
            title=pack.display_title,
            description=t(
                "billing_stars_description", credits=pack.credits, usd=int(pack.usd_amount)
            ),
            payload=invoice.payment_payload or "",
            currency="XTR",
            prices=[
                LabeledPrice(
                    label=pack.display_title, amount=int(invoice.amount_minor or pack.stars)
                )
            ],
        )
        await callback.answer()


async def on_pre_checkout(query: PreCheckoutQuery) -> None:
    await get_manager().handle_pre_checkout(query)


async def on_successful_payment(message: Message) -> None:
    await get_manager().handle_successful_payment(message)
    await send_safe(message.chat.id, t("billing_payment_success"))


async def _on_startup(*_args) -> None:
    manager = get_manager()
    await manager.ensure_indexes()
    await _schedule_reconcile(manager)


async def _schedule_reconcile(manager) -> None:
    hours = max(1, int(manager.settings.reconcile_interval_hours))
    try:
        from botspot.core.dependency_manager import get_dependency_manager

        deps = get_dependency_manager()
        scheduler = getattr(deps, "_scheduler", None)
        if scheduler is not None:
            scheduler.add_job(
                manager.reconcile,
                "interval",
                hours=hours,
                id="subscription_manager_reconcile",
                replace_existing=True,
            )
            logger.info(f"subscription reconcile scheduled every {hours}h via event_scheduler")
            return
    except Exception as e:
        logger.warning(f"event_scheduler unavailable for reconcile: {e}")
    import asyncio

    async def _loop():
        while True:
            await asyncio.sleep(hours * 3600)
            await manager.reconcile()

    asyncio.create_task(_loop())
    logger.info(f"subscription reconcile asyncio loop every {hours}h")


def setup_dispatcher(dp: Dispatcher) -> Dispatcher:
    from botspot.commands_menu import Visibility, add_command

    add_command("subscribe", "Subscribe to a plan", visibility=Visibility.PUBLIC)(cmd_subscribe)
    add_command("account", "Your plan, credits, and trial", visibility=Visibility.PUBLIC)(
        cmd_account
    )
    add_command("plans", "Subscription plans", visibility=Visibility.PUBLIC)(cmd_plans)
    add_command("buy", "Buy credit packs", visibility=Visibility.PUBLIC)(cmd_buy)
    add_command("grant", "Grant a plan", visibility=Visibility.ADMIN_ONLY)(cmd_grant)
    add_command("revoke", "Revoke a plan", visibility=Visibility.ADMIN_ONLY)(cmd_revoke)
    add_command("subscribers", "List subscribers", visibility=Visibility.ADMIN_ONLY)(
        cmd_subscribers
    )
    add_command("grant_credits", "Grant credits", visibility=Visibility.ADMIN_ONLY)(
        cmd_grant_credits
    )

    dp.message.register(cmd_subscribe, Command("subscribe"))
    dp.message.register(cmd_account, Command("account"))
    dp.message.register(cmd_plans, Command("plans"))
    dp.message.register(cmd_buy, Command("buy"))
    dp.message.register(cmd_grant, Command("grant"), AdminFilter())
    dp.message.register(cmd_revoke, Command("revoke"), AdminFilter())
    dp.message.register(cmd_subscribers, Command("subscribers"), AdminFilter())
    dp.message.register(cmd_grant_credits, Command("grant_credits"), AdminFilter())
    dp.callback_query.register(on_callback, F.data.startswith("sub:"))
    dp.pre_checkout_query.register(on_pre_checkout)
    dp.message.register(on_successful_payment, F.successful_payment)
    dp.startup.register(_on_startup)
    return dp
