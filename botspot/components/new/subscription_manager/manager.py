"""SubscriptionManager: entitlements, credits ledger, Stars, Stripe, trial."""

from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from aiogram.types import LabeledPrice, Message, PreCheckoutQuery

from botspot.components.middlewares.i18n import t
from botspot.components.new.subscription_manager.models import (
    Balance,
    CreditPack,
    Decision,
    Entitlement,
    Invoice,
    Plan,
    Subscription,
)
from botspot.components.new.subscription_manager.payloads import (
    build_invoice_payload,
    parse_invoice_payload,
)
from botspot.components.new.subscription_manager.settings import (
    KIND_PACK,
    KIND_SUBSCRIPTION,
    PAID_SOURCES,
    PROVIDER_MANUAL,
    PROVIDER_STARS,
    SOURCE_ADMIN,
    SOURCE_CREDITS,
    SOURCE_FRIEND,
    SOURCE_MANUAL,
    SOURCE_NONE,
    SOURCE_SUBSCRIPTION,
    SOURCE_TRIAL,
    STATUS_PAID,
    STATUS_PENDING,
    SUB_ACTIVE,
    SUB_CANCELLED,
    SUB_EXPIRED,
    TELEGRAM_STARS_MAX_AMOUNT,
    TELEGRAM_STARS_PERIOD_SECONDS,
    SubscriptionManagerSettings,
)
from botspot.components.new.subscription_manager import stripe as stripe_adapter
from botspot.components.new.subscription_manager import ton as ton_adapter
from botspot.components.new.subscription_manager import yookassa as yookassa_adapter
from botspot.components.new.subscription_manager.trial import (
    REASON_TRIAL_DAILY_CAP,
    TrialLimiter,
)
from botspot.core.errors import SubscriptionValidationError
from botspot.utils.internal import get_logger

logger = get_logger()

DEFAULT_PLANS = [
    Plan(
        plan_id="plus",
        title="Plus",
        stars=250,
        usd_cents=499,
        minutes_per_period=300,
        features=["summaries", "custom_instructions"],
    ),
    Plan(
        plan_id="pro",
        title="Pro",
        stars=750,
        usd_cents=1499,
        minutes_per_period=1000,
        features=["priority", "presets", "export"],
    ),
    Plan(
        plan_id="team",
        title="Team",
        stars=2000,
        usd_cents=3999,
        minutes_per_period=3000,
        seats=5,
        features=["pooled_minutes"],
    ),
]


def default_packs(credits_per_usd: int, stars_per_usd: int) -> list[CreditPack]:
    packs = []
    for usd in (10, 30, 100):
        packs.append(
            CreditPack(
                sku=f"credits_{usd}",
                credits=usd * credits_per_usd,
                usd_cents=usd * 100,
                stars=usd * stars_per_usd,
                title=f"${usd} credit pack",
            )
        )
    return packs


class SubscriptionManager:
    """Credits ledger + Stars subscriptions + plan entitlements + trial caps."""

    def __init__(
        self,
        settings: SubscriptionManagerSettings,
        db: Any,
        *,
        plans: list[Plan] | None = None,
        packs: list[CreditPack] | None = None,
        bot: Any = None,
    ):
        self.settings = settings
        self.db = db
        self._bot = bot
        self._plans = self._load_plans(plans)
        self._packs = self._load_packs(packs)
        self.trial = TrialLimiter(db, settings)

    def _load_plans(self, plans: list[Plan] | None) -> list[Plan]:
        if plans is not None:
            return list(plans)
        if self.settings.plans_json.strip():
            return [Plan.model_validate(item) for item in json.loads(self.settings.plans_json)]
        return list(DEFAULT_PLANS)

    def _load_packs(self, packs: list[CreditPack] | None) -> list[CreditPack]:
        if packs is not None:
            return list(packs)
        if self.settings.packs_json.strip():
            return [
                CreditPack.model_validate(item) for item in json.loads(self.settings.packs_json)
            ]
        return default_packs(self.credits_per_usd, self.stars_per_usd)

    @property
    def credits_per_usd(self) -> int:
        return max(1, int(self.settings.credits_per_usd))

    @property
    def stars_per_usd(self) -> int:
        return max(1, int(self.settings.stars_per_usd))

    def _coll(self, name: str):
        return self.db.get_collection(f"{self.settings.collection_prefix}{name}")

    @property
    def accounts(self):
        return self._coll("accounts")

    @property
    def ledger(self):
        return self._coll("ledger")

    @property
    def invoices(self):
        return self._coll("invoices")

    @property
    def subscriptions(self):
        return self._coll("subscriptions")

    @property
    def entitlements(self):
        return self._coll("entitlements")

    @property
    def usage_periods(self):
        return self._coll("usage_periods")

    @property
    def webhook_events(self):
        return self._coll("webhook_events")

    def bot(self):
        if self._bot is not None:
            return self._bot
        from botspot.utils.deps_getters import get_bot

        return get_bot()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    def _is_admin(self, user_id: int) -> bool:
        try:
            from botspot.utils.user_ops import is_admin

            return bool(is_admin(user_id))
        except Exception as e:
            logger.warning(f"is_admin check failed for {user_id}: {e}")
            return False

    def _is_friend(self, user_id: int) -> bool:
        try:
            from botspot.utils.user_ops import is_friend

            return bool(is_friend(user_id))
        except Exception as e:
            logger.warning(f"is_friend check failed for {user_id}: {e}")
            return False

    async def ensure_indexes(self) -> None:
        await self.accounts.create_index("telegram_user_id", unique=True)
        await self.ledger.create_index([("telegram_user_id", 1), ("created_at", -1)])
        await self.ledger.create_index(
            [("provider", 1), ("provider_charge_id", 1)], unique=True, sparse=True
        )
        await self.invoices.create_index([("telegram_user_id", 1), ("created_at", -1)])
        await self.invoices.create_index([("provider", 1), ("status", 1)])
        await self.subscriptions.create_index([("user_id", 1), ("status", 1)])
        await self.entitlements.create_index("user_id", unique=True)
        await self.webhook_events.create_index([("provider", 1), ("event_id", 1)], unique=True)
        await self.usage_periods.create_index([("user_id", 1), ("period_end", -1)])

    def list_plans(self) -> list[Plan]:
        return list(self._plans)

    def get_plan(self, plan_id: str) -> Plan:
        for plan in self._plans:
            if plan.plan_id == plan_id:
                return plan
        raise SubscriptionValidationError(f"Unknown plan: {plan_id}")

    def list_packs(self) -> list[CreditPack]:
        return list(self._packs)

    def get_pack(self, sku: str) -> CreditPack:
        for pack in self._packs:
            if pack.sku == sku:
                return pack
        raise SubscriptionValidationError(f"Unknown credit pack: {sku}")

    def credits_for_cost(self, estimated_cost_usd: float) -> int:
        cost = max(0.0, float(estimated_cost_usd))
        return max(1, int(math.ceil(cost * self.credits_per_usd)))

    def _multiplier(self, kind: str) -> float:
        if kind == "chat":
            return float(self.settings.chat_cost_multiplier)
        return float(self.settings.media_cost_multiplier)

    async def get_balance(self, user_id: int) -> Balance:
        user_id = int(user_id)
        doc = await self.accounts.find_one({"_id": user_id})
        balance = int(doc.get("balance_credits", 0)) if doc else 0
        audio_cost = float(self.settings.trial_media_cost_per_minute_usd) * float(
            self.settings.media_cost_multiplier
        )
        audio_minutes = 0.0
        if audio_cost > 0:
            audio_minutes = (balance / self.credits_per_usd) / audio_cost
        return Balance(
            telegram_user_id=user_id,
            balance_credits=balance,
            retail_usd=balance / self.credits_per_usd,
            audio_minutes=audio_minutes,
        )

    async def get_recent_ledger(self, user_id: int, limit: int = 10) -> list[dict[str, Any]]:
        cursor = (
            self.ledger.find({"telegram_user_id": int(user_id)}).sort("created_at", -1).limit(limit)
        )
        return await cursor.to_list(length=limit)

    async def check_entitlement(self, user_id: int) -> Entitlement:
        user_id = int(user_id)
        if self._is_admin(user_id):
            return Entitlement(
                user_id=user_id, source=SOURCE_ADMIN, until=None, minutes_left=None, credits=0
            )
        if self._is_friend(user_id):
            return Entitlement(
                user_id=user_id, source=SOURCE_FRIEND, until=None, minutes_left=None, credits=0
            )
        doc = await self.entitlements.find_one({"_id": user_id})
        if doc:
            ent = self._entitlement_from_doc(doc)
            if self._entitlement_still_valid(ent):
                if ent.source == SOURCE_SUBSCRIPTION:
                    ent.minutes_left = await self._minutes_left(user_id)
                return ent
        return await self._refresh_entitlement(user_id)

    def _entitlement_still_valid(self, ent: Entitlement) -> bool:
        if ent.source in {SOURCE_NONE, SOURCE_TRIAL} and ent.source != SOURCE_TRIAL:
            return ent.source != SOURCE_NONE
        if ent.source == SOURCE_CREDITS:
            return ent.credits > 0
        if ent.until is None:
            return ent.source in PAID_SOURCES
        return self._now() <= ent.until

    def _entitlement_from_doc(self, doc: dict[str, Any]) -> Entitlement:
        return Entitlement(
            user_id=int(doc.get("user_id") or doc["_id"]),
            plan_id=doc.get("plan_id"),
            source=doc.get("source") or SOURCE_NONE,
            until=doc.get("until"),
            minutes_left=doc.get("minutes_left"),
            credits=int(doc.get("credits") or 0),
        )

    async def _refresh_entitlement(self, user_id: int) -> Entitlement:
        user_id = int(user_id)
        now = self._now()
        grace = timedelta(days=int(self.settings.grace_days))
        sub = await self._active_subscription_doc(user_id)
        balance = await self.get_balance(user_id)
        if sub:
            end = sub["current_period_end"]
            until = end + grace
            if now <= until:
                minutes_left = await self._minutes_left(user_id)
                ent = Entitlement(
                    user_id=user_id,
                    plan_id=sub.get("plan_id"),
                    source=SOURCE_MANUAL
                    if sub.get("provider") == PROVIDER_MANUAL
                    else SOURCE_SUBSCRIPTION,
                    until=until,
                    minutes_left=minutes_left,
                    credits=balance.balance_credits,
                )
                if sub.get("provider") == PROVIDER_MANUAL:
                    ent.source = SOURCE_MANUAL
                await self._write_entitlement(ent)
                return ent
        if balance.balance_credits > 0:
            ent = Entitlement(
                user_id=user_id,
                source=SOURCE_CREDITS,
                until=None,
                minutes_left=None,
                credits=balance.balance_credits,
            )
            await self._write_entitlement(ent)
            return ent
        if await self.trial.is_trial_active(user_id):
            ent = Entitlement(
                user_id=user_id,
                source=SOURCE_TRIAL,
                until=None,
                minutes_left=None,
                credits=0,
            )
            await self._write_entitlement(ent)
            return ent
        ent = Entitlement(user_id=user_id, source=SOURCE_NONE, credits=0)
        await self._write_entitlement(ent)
        return ent

    async def _write_entitlement(self, ent: Entitlement) -> None:
        now = self._now()
        await self.entitlements.update_one(
            {"_id": ent.user_id},
            {
                "$set": {
                    "user_id": ent.user_id,
                    "plan_id": ent.plan_id,
                    "source": ent.source,
                    "until": ent.until,
                    "minutes_left": ent.minutes_left,
                    "credits": ent.credits,
                    "updated_at": now,
                }
            },
            upsert=True,
        )

    async def _active_subscription_doc(self, user_id: int) -> Optional[dict[str, Any]]:
        return await self.subscriptions.find_one(
            {"user_id": int(user_id), "status": {"$in": [SUB_ACTIVE, SUB_CANCELLED]}}
        )

    async def _minutes_left(self, user_id: int) -> float | None:
        period = await self._current_usage_period(user_id)
        if not period:
            return None
        cap = period.get("minutes_cap")
        if cap is None:
            return None
        used = float(period.get("minutes_used") or 0)
        return max(0.0, float(cap) - used)

    async def _current_usage_period(self, user_id: int) -> Optional[dict[str, Any]]:
        now = self._now()
        return await self.usage_periods.find_one(
            {"user_id": int(user_id), "period_start": {"$lte": now}, "period_end": {"$gte": now}}
        )

    async def authorize(
        self,
        user_id: int,
        *,
        kind: str,
        estimated_minutes: float = 0,
        estimated_tokens: int = 0,
        estimated_cost_usd: float = 0,
        weight: float = 1.0,
    ) -> Decision:
        user_id = int(user_id)
        if self._is_admin(user_id):
            return Decision(allowed=True, source=SOURCE_ADMIN, reason="admin bypass")
        if self._is_friend(user_id):
            return Decision(allowed=True, source=SOURCE_FRIEND, reason="friend bypass")

        needed_minutes = float(estimated_minutes) * float(weight) if kind == "audio" else 0.0
        sub = await self._active_subscription_doc(user_id)
        if sub and self._subscription_in_grace(sub):
            minutes_left = await self._minutes_left(user_id)
            if needed_minutes <= 0 or minutes_left is None or needed_minutes <= minutes_left:
                hold_id = await self._open_hold(
                    user_id,
                    source=SOURCE_SUBSCRIPTION,
                    kind=kind,
                    credits=0,
                    estimated_cost_usd=estimated_cost_usd,
                    estimated_minutes=needed_minutes,
                    weight=weight,
                )
                return Decision(allowed=True, source=SOURCE_SUBSCRIPTION, hold_id=hold_id)

        hold_usd = float(estimated_cost_usd) * self._multiplier(kind)
        credits = self.credits_for_cost(hold_usd)
        hold_id = await self._try_debit_credits(user_id, credits, kind, hold_usd)
        if hold_id:
            return Decision(allowed=True, source=SOURCE_CREDITS, hold_id=hold_id)

        trial = await self.trial.reserve(
            user_id,
            kind=kind,
            estimated_minutes=estimated_minutes,
            estimated_tokens=estimated_tokens,
            estimated_cost_usd=estimated_cost_usd,
        )
        if trial.allowed:
            return Decision(allowed=True, source=SOURCE_TRIAL, reason="trial")
        return self._deny_authorize(trial, sub, credits, needed_minutes)

    def _deny_authorize(self, trial, sub, credits: int, needed_minutes: float) -> Decision:
        if trial.message_key == REASON_TRIAL_DAILY_CAP:
            minutes_left = (
                0.0 if trial.minutes_left_today is None else float(trial.minutes_left_today)
            )
            resets_at = trial.resets_at or ""
            return Decision(
                allowed=False,
                source=SOURCE_NONE,
                reason=REASON_TRIAL_DAILY_CAP,
                message_key=REASON_TRIAL_DAILY_CAP,
                user_message=t(
                    REASON_TRIAL_DAILY_CAP,
                    minutes_left=f"{minutes_left:.1f}",
                    resets_at=resets_at,
                ),
            )
        if sub and needed_minutes > 0:
            message_key = "subscription_minutes_exhausted"
        elif credits:
            message_key = trial.message_key or "billing_insufficient_credits"
        else:
            message_key = trial.message_key or "subscription_no_access"
        if trial.message_key:
            message_key = (
                trial.message_key
                if message_key != "subscription_minutes_exhausted"
                else message_key
            )
            if not sub:
                message_key = trial.message_key
        return Decision(
            allowed=False,
            source=SOURCE_NONE,
            reason=t(message_key) if message_key else "denied",
            message_key=message_key or "subscription_no_access",
        )

    def _subscription_in_grace(self, sub: dict[str, Any]) -> bool:
        end = sub.get("current_period_end")
        if not isinstance(end, datetime):
            return False
        return self._now() <= end + timedelta(days=int(self.settings.grace_days))

    async def settle(
        self,
        hold_id: str,
        *,
        actual_cost_usd: float,
        actual_minutes: float = 0,
        actual_tokens: int = 0,
    ) -> None:
        hold = await self.ledger.find_one({"_id": hold_id})
        if not hold or hold.get("kind") != "hold" or hold.get("settled_at"):
            return
        source = hold.get("source")
        user_id = int(hold["telegram_user_id"])
        if source == SOURCE_SUBSCRIPTION:
            minutes = float(actual_minutes) * float(hold.get("weight") or 1.0)
            if minutes > 0:
                await self.consume_minutes(user_id, minutes, weight=1.0)
        elif source == SOURCE_CREDITS:
            held = abs(int(hold.get("amount_credits") or 0))
            actual_credits = self.credits_for_cost(actual_cost_usd)
            unused = held - actual_credits
            if unused > 0:
                await self._credit_back_hold(hold_id, unused, reason="settle:actual")
        await self.ledger.update_one(
            {"_id": hold_id},
            {
                "$set": {
                    "settled_at": self._now(),
                    "actual_cost_usd": float(actual_cost_usd),
                    "actual_minutes": float(actual_minutes),
                    "actual_tokens": int(actual_tokens),
                }
            },
        )
        await self._refresh_entitlement(user_id)

    async def release(self, hold_id: str) -> None:
        hold = await self.ledger.find_one({"_id": hold_id})
        if not hold or hold.get("kind") != "hold" or hold.get("settled_at"):
            return
        if hold.get("source") == SOURCE_CREDITS:
            held = abs(int(hold.get("amount_credits") or 0))
            if held > 0:
                await self._credit_back_hold(hold_id, held, reason="release")
        await self.ledger.update_one(
            {"_id": hold_id},
            {"$set": {"settled_at": self._now(), "released": True}},
        )
        await self._refresh_entitlement(int(hold["telegram_user_id"]))

    async def consume_minutes(self, user_id: int, minutes: float, weight: float = 1.0) -> None:
        charged = float(minutes) * float(weight)
        if charged <= 0:
            return
        period = await self._current_usage_period(user_id)
        if not period:
            return
        await self.usage_periods.update_one(
            {"_id": period["_id"]},
            {"$inc": {"minutes_used": charged}, "$set": {"updated_at": self._now()}},
        )
        await self._refresh_entitlement(user_id)

    async def grant_admin_credits(
        self, user_id: int, credits: int, granted_by: int, note: str = ""
    ) -> str:
        if credits <= 0:
            raise SubscriptionValidationError("Credits must be positive.")
        user_id = int(user_id)
        now = self._now()
        ledger_id = f"admin_gift:{user_id}:{uuid.uuid4().hex}"
        await self.ledger.insert_one(
            {
                "_id": ledger_id,
                "telegram_user_id": user_id,
                "kind": "credit",
                "source": "admin_gift",
                "amount_credits": int(credits),
                "metadata": {"admin_user_id": int(granted_by), "note": note},
                "created_at": now,
            }
        )
        await self._ensure_account(user_id)
        await self.accounts.update_one(
            {"_id": user_id},
            {"$inc": {"balance_credits": int(credits)}, "$set": {"updated_at": now}},
        )
        await self._refresh_entitlement(user_id)
        return ledger_id

    async def create_stars_subscription_link(self, user_id: int, plan_id: str) -> str:
        plan = self.get_plan(plan_id)
        if plan.period_days != 30:
            raise SubscriptionValidationError(
                "Telegram Stars subscriptions require period_days == 30"
            )
        if plan.stars > TELEGRAM_STARS_MAX_AMOUNT:
            raise SubscriptionValidationError("plan.stars must be <= 10000")
        invoice = await self._create_invoice(
            provider=PROVIDER_STARS,
            user_id=user_id,
            sku=plan.plan_id,
            title=plan.title,
            credits=int(plan.credits_per_period or 0),
            amount_minor=plan.stars,
            currency="XTR",
            status=STATUS_PENDING,
            kind=KIND_SUBSCRIPTION,
            plan_id=plan.plan_id,
        )
        payload = build_invoice_payload(
            self.settings, PROVIDER_STARS, invoice.invoice_id, int(user_id)
        )
        await self.invoices.update_one(
            {"_id": invoice.invoice_id},
            {"$set": {"payment_payload": payload, "updated_at": self._now()}},
        )
        link = await self.bot().create_invoice_link(
            title=plan.title,
            description=t("subscription_stars_description", title=plan.title, stars=plan.stars),
            payload=payload,
            currency="XTR",
            prices=[LabeledPrice(label=plan.title, amount=plan.stars)],
            subscription_period=TELEGRAM_STARS_PERIOD_SECONDS,
        )
        return link

    async def create_stars_invoice(self, user_id: int, sku: str) -> Invoice:
        pack = self.get_pack(sku)
        stars_amount = pack.stars or max(1, int(round(pack.usd_amount * self.stars_per_usd)))
        invoice = await self._create_invoice(
            provider=PROVIDER_STARS,
            user_id=user_id,
            sku=pack.sku,
            title=pack.display_title,
            credits=pack.credits,
            amount_minor=stars_amount,
            currency="XTR",
            status=STATUS_PENDING,
            kind=KIND_PACK,
        )
        payload = build_invoice_payload(
            self.settings, PROVIDER_STARS, invoice.invoice_id, int(user_id)
        )
        await self.invoices.update_one(
            {"_id": invoice.invoice_id},
            {"$set": {"payment_payload": payload, "updated_at": self._now()}},
        )
        invoice.payment_payload = payload
        return invoice

    async def handle_pre_checkout(self, query: PreCheckoutQuery) -> None:
        try:
            parsed = parse_invoice_payload(
                self.settings, query.invoice_payload, expected_provider=PROVIDER_STARS
            )
        except SubscriptionValidationError:
            await query.answer(ok=False, error_message=t("billing_invoice_invalid"))
            return
        invoice = await self.invoices.find_one(
            {
                "_id": parsed["invoice_id"],
                "telegram_user_id": parsed["telegram_user_id"],
                "provider": PROVIDER_STARS,
            }
        )
        if not invoice:
            await query.answer(ok=False, error_message=t("billing_invoice_not_found"))
            return
        await query.answer(ok=True)

    async def handle_successful_payment(self, message: Message) -> Entitlement:
        sp = message.successful_payment
        assert sp is not None
        parsed = parse_invoice_payload(
            self.settings, sp.invoice_payload, expected_provider=PROVIDER_STARS
        )
        invoice = await self.invoices.find_one(
            {
                "_id": parsed["invoice_id"],
                "telegram_user_id": parsed["telegram_user_id"],
                "provider": PROVIDER_STARS,
            }
        )
        if not invoice:
            raise SubscriptionValidationError("Stars invoice not found.")
        charge_id = sp.telegram_payment_charge_id or sp.provider_payment_charge_id
        if not charge_id:
            charge_id = f"stars:{parsed['invoice_id']}"
        user_id = int(parsed["telegram_user_id"])
        is_sub = (
            bool(sp.is_recurring)
            or bool(sp.is_first_recurring)
            or invoice.get("kind") == KIND_SUBSCRIPTION
        )
        if is_sub:
            period_end = None
            if sp.subscription_expiration_date:
                period_end = datetime.fromtimestamp(
                    int(sp.subscription_expiration_date), tz=timezone.utc
                ).replace(tzinfo=None)
            plan_id = str(invoice.get("plan_id") or invoice.get("sku"))
            await self._activate_subscription(
                user_id=user_id,
                plan_id=plan_id,
                provider=PROVIDER_STARS,
                provider_sub_id=charge_id,
                provider_charge_id=charge_id,
                period_end=period_end,
            )
            await self._grant_invoice_credits(
                invoice={**invoice, "credits": 0},
                provider_event_id=f"stars:{charge_id}",
                metadata={
                    "telegram_payment_charge_id": sp.telegram_payment_charge_id,
                    "is_recurring": sp.is_recurring,
                    "is_first_recurring": sp.is_first_recurring,
                },
                skip_credits=True,
            )
        else:
            await self._grant_invoice_credits(
                invoice=invoice,
                provider_event_id=f"stars:{charge_id}",
                metadata={
                    "telegram_payment_charge_id": sp.telegram_payment_charge_id,
                    "provider_payment_charge_id": sp.provider_payment_charge_id,
                },
            )
        now = self._now()
        await self.invoices.update_one(
            {"_id": parsed["invoice_id"]},
            {
                "$set": {
                    "status": STATUS_PAID,
                    "paid_at": now,
                    "telegram_payment_charge_id": sp.telegram_payment_charge_id,
                    "provider_payment_charge_id": sp.provider_payment_charge_id,
                    "updated_at": now,
                }
            },
        )
        return await self.check_entitlement(user_id)

    async def cancel_subscription(self, user_id: int, *, at_period_end: bool = True) -> None:
        sub = await self._active_subscription_doc(user_id)
        if not sub:
            raise SubscriptionValidationError("No active subscription.")
        if sub.get("provider") == PROVIDER_STARS and sub.get("provider_charge_id"):
            await self.bot().edit_user_star_subscription(
                user_id=int(user_id),
                telegram_payment_charge_id=str(sub["provider_charge_id"]),
                is_canceled=True,
            )
        now = self._now()
        update: dict[str, Any] = {"cancel_at_period_end": True, "updated_at": now}
        if not at_period_end:
            update["status"] = SUB_EXPIRED
        else:
            update["status"] = SUB_CANCELLED
        await self.subscriptions.update_one({"_id": sub["_id"]}, {"$set": update})
        await self._refresh_entitlement(int(user_id))

    async def refund(self, user_id: int, provider_charge_id: str) -> None:
        await self.bot().refund_star_payment(
            user_id=int(user_id), telegram_payment_charge_id=provider_charge_id
        )
        now = self._now()
        event_key = f"refund:stars:{provider_charge_id}"
        result = await self.ledger.update_one(
            {"_id": event_key},
            {
                "$setOnInsert": {
                    "_id": event_key,
                    "telegram_user_id": int(user_id),
                    "kind": "debit",
                    "source": "refund:stars",
                    "provider": PROVIDER_STARS,
                    "provider_charge_id": f"refund:{provider_charge_id}",
                    "amount_credits": 0,
                    "created_at": now,
                }
            },
            upsert=True,
        )
        if getattr(result, "upserted_id", None) is None:
            return
        sub = await self.subscriptions.find_one(
            {"user_id": int(user_id), "provider_charge_id": provider_charge_id}
        )
        if sub:
            await self.subscriptions.update_one(
                {"_id": sub["_id"]},
                {"$set": {"status": SUB_EXPIRED, "updated_at": now}},
            )
        payment = await self.ledger.find_one(
            {"provider": PROVIDER_STARS, "provider_charge_id": provider_charge_id}
        )
        if payment and int(payment.get("amount_credits") or 0) > 0:
            credits = int(payment["amount_credits"])
            await self.accounts.update_one(
                {"_id": int(user_id)},
                {"$inc": {"balance_credits": -credits}, "$set": {"updated_at": now}},
            )
        await self._refresh_entitlement(int(user_id))

    async def reconcile(self) -> dict[str, int]:
        now = self._now()
        grace = timedelta(days=int(self.settings.grace_days))
        expired = 0
        cursor = self.subscriptions.find({"status": {"$in": [SUB_ACTIVE, SUB_CANCELLED]}})
        subs = await cursor.to_list(length=10000)
        for sub in subs:
            end = sub.get("current_period_end")
            if isinstance(end, datetime) and now > end + grace:
                await self.subscriptions.update_one(
                    {"_id": sub["_id"]},
                    {"$set": {"status": SUB_EXPIRED, "updated_at": now}},
                )
                await self._refresh_entitlement(int(sub["user_id"]))
                expired += 1
        credited = await self._reconcile_star_transactions()
        logger.info(f"subscription reconcile: expired={expired} star_credits={credited}")
        return {"expired": expired, "star_credits": credited}

    async def _reconcile_star_transactions(self) -> int:
        credited = 0
        offset = 0
        bot = self.bot()
        while True:
            page = await bot.get_star_transactions(offset=offset, limit=100)
            txs = list(getattr(page, "transactions", None) or [])
            if not txs:
                break
            for tx in txs:
                source = getattr(tx, "source", None)
                payload = getattr(source, "invoice_payload", None) if source is not None else None
                if not payload:
                    continue
                try:
                    parsed = parse_invoice_payload(
                        self.settings, payload, expected_provider=PROVIDER_STARS
                    )
                except SubscriptionValidationError:
                    continue
                charge_id = str(getattr(tx, "id", "") or "")
                if not charge_id:
                    continue
                existing = await self.ledger.find_one({"_id": f"payment:stars:{charge_id}"})
                if existing:
                    continue
                invoice = await self.invoices.find_one({"_id": parsed["invoice_id"]})
                if not invoice:
                    continue
                if invoice.get("kind") == KIND_SUBSCRIPTION:
                    await self._activate_subscription(
                        user_id=int(parsed["telegram_user_id"]),
                        plan_id=str(invoice.get("plan_id") or invoice.get("sku")),
                        provider=PROVIDER_STARS,
                        provider_sub_id=charge_id,
                        provider_charge_id=charge_id,
                        period_end=None,
                    )
                    await self._grant_invoice_credits(
                        invoice={**invoice, "credits": 0},
                        provider_event_id=f"stars:{charge_id}",
                        skip_credits=True,
                    )
                else:
                    await self._grant_invoice_credits(
                        invoice=invoice, provider_event_id=f"stars:{charge_id}"
                    )
                credited += 1
            if len(txs) < 100:
                break
            offset += len(txs)
        return credited

    async def grant(
        self, user_id: int, plan_id: str, *, days: int | None, granted_by: int, note: str = ""
    ) -> Subscription:
        plan = self.get_plan(plan_id)
        period_days = int(days if days is not None else plan.period_days)
        now = self._now()
        period_end = now + timedelta(days=period_days)
        sub = await self._activate_subscription(
            user_id=int(user_id),
            plan_id=plan.plan_id,
            provider=PROVIDER_MANUAL,
            provider_sub_id=f"manual:{user_id}:{uuid.uuid4().hex}",
            provider_charge_id="",
            period_end=period_end,
            granted_by=int(granted_by),
            note=note,
        )
        return sub

    async def revoke(self, user_id: int, *, granted_by: int) -> None:
        now = self._now()
        await self.subscriptions.update_many(
            {"user_id": int(user_id), "status": {"$in": [SUB_ACTIVE, SUB_CANCELLED]}},
            {"$set": {"status": SUB_EXPIRED, "revoked_by": int(granted_by), "updated_at": now}},
        )
        await self._refresh_entitlement(int(user_id))

    async def list_subscribers(self, status: str = SUB_ACTIVE) -> list[Subscription]:
        records = await self.subscriptions.find({"status": status}).to_list(length=1000)
        return [self._subscription_from_doc(r) for r in records]

    def create_stripe_checkout(
        self, user_id: int, *, sku: str | None = None, plan_id: str | None = None
    ):
        return stripe_adapter.create_stripe_checkout(self, user_id, sku=sku, plan_id=plan_id)

    def verify_stripe_webhook(self, raw_body: bytes, signature: str) -> dict:
        return stripe_adapter.verify_stripe_webhook(self, raw_body, signature)

    def handle_stripe_event(self, event: dict[str, Any]):
        return stripe_adapter.handle_stripe_event(self, event)

    def create_yookassa_payment(self, user_id: int, sku: str):
        return yookassa_adapter.create_yookassa_payment(self, user_id, sku)

    def handle_yookassa_event(self, event: dict[str, Any]):
        return yookassa_adapter.handle_yookassa_event(self, event)

    def create_ton_manual_invoice(self, user_id: int, sku: str):
        return ton_adapter.create_ton_manual_invoice(self, user_id, sku)

    def record_ton_proof(self, user_id: int, invoice_id: str, proof_text: str):
        return ton_adapter.record_ton_proof(self, user_id, invoice_id, proof_text)

    def confirm_manual_invoice(self, invoice_id: str, admin_user_id: int):
        return ton_adapter.confirm_manual_invoice(self, invoice_id, admin_user_id)

    async def _activate_subscription(
        self,
        *,
        user_id: int,
        plan_id: str,
        provider: str,
        provider_sub_id: str,
        provider_charge_id: str,
        period_end: datetime | None,
        granted_by: int | None = None,
        note: str = "",
    ) -> Subscription:
        plan = self.get_plan(plan_id)
        now = self._now()
        if period_end is None:
            period_end = now + timedelta(days=plan.period_days)
        existing = await self.subscriptions.find_one(
            {"user_id": int(user_id), "status": {"$in": [SUB_ACTIVE, SUB_CANCELLED]}}
        )
        doc = {
            "user_id": int(user_id),
            "plan_id": plan.plan_id,
            "provider": provider,
            "provider_sub_id": provider_sub_id,
            "provider_charge_id": provider_charge_id
            or (existing or {}).get("provider_charge_id")
            or "",
            "status": SUB_ACTIVE,
            "started_at": (existing or {}).get("started_at") or now,
            "current_period_end": period_end,
            "cancel_at_period_end": False,
            "granted_by": granted_by,
            "note": note,
            "updated_at": now,
        }
        if existing:
            await self.subscriptions.update_one({"_id": existing["_id"]}, {"$set": doc})
            doc["_id"] = existing["_id"]
        else:
            doc["_id"] = f"{user_id}:{plan.plan_id}:{uuid.uuid4().hex}"
            doc["created_at"] = now
            await self.subscriptions.insert_one(doc)
        await self._open_usage_period(user_id, plan, period_end)
        if provider_charge_id:
            await self.ledger.update_one(
                {"_id": f"payment:{provider}:{provider_charge_id}"},
                {
                    "$setOnInsert": {
                        "_id": f"payment:{provider}:{provider_charge_id}",
                        "telegram_user_id": int(user_id),
                        "kind": "credit",
                        "source": f"subscription:{provider}",
                        "provider": provider,
                        "provider_charge_id": provider_charge_id,
                        "plan_id": plan.plan_id,
                        "amount_credits": 0,
                        "created_at": now,
                    }
                },
                upsert=True,
            )
        await self._refresh_entitlement(int(user_id))
        return self._subscription_from_doc(doc)

    async def _renew_subscription_by_provider_sub(
        self,
        *,
        provider: str,
        provider_sub_id: str,
        provider_charge_id: str,
        period_end: datetime | None,
    ) -> bool:
        sub = await self.subscriptions.find_one(
            {"provider": provider, "provider_sub_id": provider_sub_id}
        )
        if not sub:
            return False
        await self._activate_subscription(
            user_id=int(sub["user_id"]),
            plan_id=str(sub["plan_id"]),
            provider=provider,
            provider_sub_id=provider_sub_id,
            provider_charge_id=provider_charge_id,
            period_end=period_end,
        )
        return True

    async def _cancel_by_provider_sub(self, provider: str, provider_sub_id: str) -> bool:
        sub = await self.subscriptions.find_one(
            {"provider": provider, "provider_sub_id": provider_sub_id}
        )
        if not sub:
            return False
        now = self._now()
        await self.subscriptions.update_one(
            {"_id": sub["_id"]},
            {"$set": {"status": SUB_CANCELLED, "cancel_at_period_end": True, "updated_at": now}},
        )
        await self._refresh_entitlement(int(sub["user_id"]))
        return True

    async def _open_usage_period(self, user_id: int, plan: Plan, period_end: datetime) -> None:
        now = self._now()
        period_id = f"{user_id}:{plan.plan_id}:{period_end.isoformat()}"
        await self.usage_periods.update_one(
            {"_id": period_id},
            {
                "$setOnInsert": {
                    "user_id": int(user_id),
                    "plan_id": plan.plan_id,
                    "period_start": now,
                    "period_end": period_end,
                    "minutes_used": 0.0,
                    "minutes_cap": plan.minutes_per_period,
                    "created_at": now,
                },
                "$set": {
                    "updated_at": now,
                    "minutes_cap": plan.minutes_per_period,
                    "period_end": period_end,
                },
            },
            upsert=True,
        )

    def _subscription_from_doc(self, doc: dict[str, Any]) -> Subscription:
        return Subscription(
            user_id=int(doc["user_id"]),
            plan_id=str(doc["plan_id"]),
            provider=doc.get("provider") or PROVIDER_MANUAL,
            provider_sub_id=str(doc.get("provider_sub_id") or ""),
            provider_charge_id=str(doc.get("provider_charge_id") or ""),
            status=doc.get("status") or SUB_ACTIVE,
            started_at=doc["started_at"],
            current_period_end=doc["current_period_end"],
            cancel_at_period_end=bool(doc.get("cancel_at_period_end")),
            granted_by=doc.get("granted_by"),
        )

    async def _open_hold(
        self,
        user_id: int,
        *,
        source: str,
        kind: str,
        credits: int,
        estimated_cost_usd: float,
        estimated_minutes: float,
        weight: float,
    ) -> str:
        hold_id = f"hold:{user_id}:{uuid.uuid4().hex}"
        now = self._now()
        await self.ledger.insert_one(
            {
                "_id": hold_id,
                "telegram_user_id": int(user_id),
                "kind": "hold",
                "source": source,
                "usage_type": kind,
                "amount_credits": -int(credits),
                "estimated_cost_usd": float(estimated_cost_usd),
                "estimated_minutes": float(estimated_minutes),
                "weight": float(weight),
                "created_at": now,
            }
        )
        return hold_id

    async def _try_debit_credits(
        self, user_id: int, credits: int, kind: str, estimated_cost_usd: float
    ) -> Optional[str]:
        await self._ensure_account(user_id)
        now = self._now()
        result = await self.accounts.update_one(
            {"_id": user_id, "balance_credits": {"$gte": credits}},
            {"$inc": {"balance_credits": -credits}, "$set": {"updated_at": now}},
        )
        if int(getattr(result, "modified_count", 0)) == 0:
            return None
        return await self._open_hold(
            user_id,
            source=SOURCE_CREDITS,
            kind=kind,
            credits=credits,
            estimated_cost_usd=estimated_cost_usd,
            estimated_minutes=0,
            weight=1.0,
        )

    async def _credit_back_hold(self, hold_id: str, credits: int, reason: str) -> bool:
        if credits <= 0:
            return False
        hold = await self.ledger.find_one({"_id": hold_id})
        if not hold or hold.get("refunded_at"):
            return False
        refund_key = f"refund:{hold_id}"
        now = self._now()
        insert_result = await self.ledger.update_one(
            {"_id": refund_key},
            {
                "$setOnInsert": {
                    "_id": refund_key,
                    "telegram_user_id": int(hold["telegram_user_id"]),
                    "kind": "credit",
                    "source": "settle:usage" if reason.startswith("settle") else "refund:usage",
                    "usage_ledger_id": hold_id,
                    "amount_credits": credits,
                    "reason": reason,
                    "created_at": now,
                }
            },
            upsert=True,
        )
        if getattr(insert_result, "upserted_id", None) is None:
            return False
        await self.accounts.update_one(
            {"_id": int(hold["telegram_user_id"])},
            {"$inc": {"balance_credits": credits}, "$set": {"updated_at": now}},
        )
        await self.ledger.update_one(
            {"_id": hold_id},
            {"$set": {"refunded_at": now, "refund_ledger_id": refund_key, "refund_reason": reason}},
        )
        return True

    async def _grant_invoice_credits(
        self,
        invoice: dict[str, Any],
        provider_event_id: str,
        metadata: Optional[dict[str, Any]] = None,
        skip_credits: bool = False,
    ) -> bool:
        event_key = f"payment:{provider_event_id}"
        existing = await self.ledger.find_one({"_id": event_key})
        if existing:
            return False
        user_id = int(invoice["telegram_user_id"])
        credits = 0 if skip_credits else int(invoice.get("credits") or 0)
        now = self._now()
        provider = str(invoice.get("provider") or "")
        insert_result = await self.ledger.update_one(
            {"_id": event_key},
            {
                "$setOnInsert": {
                    "_id": event_key,
                    "telegram_user_id": user_id,
                    "kind": "credit",
                    "source": f"payment:{provider}",
                    "provider": provider,
                    "provider_charge_id": provider_event_id,
                    "invoice_id": invoice["_id"],
                    "sku": invoice.get("sku"),
                    "amount_credits": credits,
                    "amount_minor": invoice.get("amount_minor"),
                    "amount_decimal": invoice.get("amount_decimal"),
                    "currency": invoice.get("currency"),
                    "metadata": metadata or {},
                    "created_at": now,
                }
            },
            upsert=True,
        )
        if getattr(insert_result, "upserted_id", None) is None:
            return False
        if credits > 0:
            await self._ensure_account(user_id)
            await self.accounts.update_one(
                {"_id": user_id},
                {"$inc": {"balance_credits": credits}, "$set": {"updated_at": now}},
            )
        await self._refresh_entitlement(user_id)
        return True

    async def _create_invoice(
        self,
        *,
        provider: str,
        user_id: int,
        sku: str,
        title: str,
        credits: int,
        currency: str,
        status: str,
        amount_minor: int | None = None,
        amount_decimal: str | None = None,
        kind: str = KIND_PACK,
        plan_id: str | None = None,
        ton_wallet_address: str | None = None,
        username: str | None = None,
    ) -> Invoice:
        now = self._now()
        invoice_id = uuid.uuid4().hex
        doc = {
            "_id": invoice_id,
            "provider": provider,
            "sku": sku,
            "title": title,
            "telegram_user_id": int(user_id),
            "username": username,
            "credits": credits,
            "amount_minor": amount_minor,
            "amount_decimal": amount_decimal,
            "currency": currency,
            "status": status,
            "kind": kind,
            "plan_id": plan_id,
            "ton_wallet_address": ton_wallet_address,
            "created_at": now,
            "updated_at": now,
        }
        await self.invoices.insert_one(doc)
        await self._ensure_account(int(user_id), username=username)
        return self._invoice_from_doc(doc)

    async def _fail_invoice(self, invoice_id: str, error: str) -> None:
        await self.invoices.update_one(
            {"_id": invoice_id},
            {"$set": {"status": "failed", "provider_error": error, "updated_at": self._now()}},
        )

    async def _ensure_account(self, user_id: int, username: Optional[str] = None) -> None:
        now = self._now()
        await self.accounts.update_one(
            {"_id": int(user_id)},
            {
                "$setOnInsert": {
                    "telegram_user_id": int(user_id),
                    "balance_credits": 0,
                    "status": "active",
                    "created_at": now,
                },
                "$set": {"username": username, "updated_at": now},
            },
            upsert=True,
        )

    async def _record_webhook_event(self, provider: str, event_id: str) -> bool:
        result = await self.webhook_events.update_one(
            {"_id": f"{provider}:{event_id}"},
            {
                "$setOnInsert": {
                    "provider": provider,
                    "event_id": event_id,
                    "created_at": self._now(),
                }
            },
            upsert=True,
        )
        return getattr(result, "upserted_id", None) is not None

    def _invoice_from_doc(self, doc: dict[str, Any]) -> Invoice:
        return Invoice(
            invoice_id=str(doc["_id"]),
            provider=str(doc["provider"]),
            sku=str(doc["sku"]),
            title=str(doc["title"]),
            telegram_user_id=int(doc["telegram_user_id"]),
            username=doc.get("username"),
            credits=int(doc.get("credits") or 0),
            amount_minor=doc.get("amount_minor"),
            amount_decimal=doc.get("amount_decimal"),
            currency=str(doc["currency"]),
            status=str(doc["status"]),
            payment_payload=doc.get("payment_payload"),
            checkout_url=doc.get("checkout_url"),
            ton_wallet_address=doc.get("ton_wallet_address"),
            ton_memo=doc.get("ton_memo"),
            plan_id=doc.get("plan_id"),
            kind=str(doc.get("kind") or KIND_PACK),
        )
