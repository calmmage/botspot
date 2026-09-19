"""Tests for subscription_manager. No Telegram token or network required."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from botspot.components.new.subscription_manager import (
    STRIPE_WEBHOOK_PATH,
    Balance,
    CreditPack,
    Decision,
    Entitlement,
    Plan,
    SubscriptionManager,
    SubscriptionManagerSettings,
    aiohttp_routes,
    require_plan,
)
from botspot.components.new.subscription_manager.payloads import (
    build_invoice_payload,
    parse_invoice_payload,
)
from botspot.components.new.subscription_manager.settings import (
    PROVIDER_STARS,
    PROVIDER_STRIPE,
    SOURCE_ADMIN,
    SOURCE_CREDITS,
    SOURCE_FRIEND,
    SOURCE_NONE,
    SOURCE_SUBSCRIPTION,
    SOURCE_TRIAL,
    TELEGRAM_STARS_PERIOD_SECONDS,
)
from botspot.core.errors import (
    ConfigurationError,
    SubscriptionPaymentError,
    SubscriptionValidationError,
)


class FakeUpdateResult:
    def __init__(self, modified_count=0, upserted_id=None):
        self.modified_count = modified_count
        self.upserted_id = upserted_id


class FakeCursor:
    def __init__(self, docs):
        self.docs = list(docs)

    def sort(self, key, direction):
        reverse = direction < 0
        self.docs.sort(key=lambda doc: doc.get(key) or datetime.min, reverse=reverse)
        return self

    def limit(self, limit):
        self.docs = self.docs[:limit]
        return self

    async def to_list(self, length):
        return self.docs[:length]


class FakeCollection:
    def __init__(self):
        self.docs = {}
        self.indexes = []

    async def create_index(self, keys, **kwargs):
        self.indexes.append((keys, kwargs))
        return str(keys)

    async def find_one(self, query):
        for doc in self.docs.values():
            if self._matches(doc, query):
                return dict(doc)
        return None

    def find(self, query):
        return FakeCursor([dict(doc) for doc in self.docs.values() if self._matches(doc, query)])

    async def insert_one(self, doc):
        self.docs[doc["_id"]] = dict(doc)
        return SimpleNamespace(inserted_id=doc["_id"])

    async def update_one(self, query, update, upsert=False):
        matched_key = None
        for key, doc in self.docs.items():
            if self._matches(doc, query):
                matched_key = key
                break
        upserted_id = None
        if matched_key is None:
            if not upsert:
                return FakeUpdateResult(modified_count=0)
            doc = {}
            for key, value in query.items():
                if not isinstance(value, dict):
                    doc[key] = value
            if "_id" not in doc:
                doc["_id"] = query.get("_id")
            matched_key = doc["_id"]
            self.docs[matched_key] = doc
            upserted_id = matched_key
        doc = self.docs[matched_key]
        for key, value in update.get("$setOnInsert", {}).items():
            if upserted_id is not None:
                doc[key] = value
        for key, value in update.get("$set", {}).items():
            doc[key] = value
        for key, value in update.get("$inc", {}).items():
            doc[key] = doc.get(key, 0) + value
        return FakeUpdateResult(modified_count=1, upserted_id=upserted_id)

    async def update_many(self, query, update):
        count = 0
        for doc in self.docs.values():
            if self._matches(doc, query):
                for key, value in update.get("$set", {}).items():
                    doc[key] = value
                count += 1
        return FakeUpdateResult(modified_count=count)

    def _matches(self, doc, query):
        for key, value in query.items():
            current = doc.get(key)
            if isinstance(value, dict):
                if "$gte" in value and not (current is not None and current >= value["$gte"]):
                    return False
                if "$lte" in value and not (current is not None and current <= value["$lte"]):
                    return False
                if "$in" in value and current not in value["$in"]:
                    return False
                continue
            if current != value:
                return False
        return True


class FakeDb:
    def __init__(self):
        self.collections = {}

    def get_collection(self, name):
        self.collections.setdefault(name, FakeCollection())
        return self.collections[name]


class FakeBot:
    def __init__(self):
        self.invoice_links = []
        self.edits = []
        self.refunds = []
        self.messages = []
        self.usernames: dict[int, str] = {}
        self.star_transactions = SimpleNamespace(transactions=[])

    async def create_invoice_link(self, **kwargs):
        self.invoice_links.append(kwargs)
        return "https://example.com/stars-invoice"

    async def edit_user_star_subscription(self, **kwargs):
        self.edits.append(kwargs)
        return True

    async def refund_star_payment(self, **kwargs):
        self.refunds.append(kwargs)
        return True

    async def get_star_transactions(self, offset=None, limit=None):
        return self.star_transactions

    async def send_invoice(self, **kwargs):
        return SimpleNamespace(message_id=1)

    async def send_message(self, chat_id, text, **kwargs):
        self.messages.append({"chat_id": chat_id, "text": text, **kwargs})
        return SimpleNamespace(message_id=len(self.messages))

    async def get_chat(self, chat_id):
        return SimpleNamespace(id=chat_id, username=self.usernames.get(int(chat_id)))


def _settings(**overrides) -> SubscriptionManagerSettings:
    data = {
        "enabled": True,
        "signature_secret": SecretStr("test-secret"),
        "public_base_url": "https://example.com",
    }
    data.update(overrides)
    return SubscriptionManagerSettings(**data)


def _manager(**overrides) -> SubscriptionManager:
    bot = overrides.pop("bot", FakeBot())
    db = overrides.pop("db", FakeDb())
    settings = overrides.pop("settings", None) or _settings(**overrides.pop("settings_kwargs", {}))
    return SubscriptionManager(settings, db=db, bot=bot, **overrides)


@pytest.fixture
def manager():
    return _manager()


def test_settings_env_prefix(monkeypatch):
    monkeypatch.setenv("BOTSPOT_SUBSCRIPTION_MANAGER_ENABLED", "true")
    monkeypatch.setenv("BOTSPOT_SUBSCRIPTION_MANAGER_GRACE_DAYS", "4")
    monkeypatch.setenv("BOTSPOT_SUBSCRIPTION_MANAGER_CREDITS_PER_USD", "50")
    settings = SubscriptionManagerSettings()
    assert settings.enabled is True
    assert settings.grace_days == 4
    assert settings.credits_per_usd == 50


def test_default_packs_and_plans(manager):
    packs = manager.list_packs()
    assert [p.sku for p in packs] == ["credits_10", "credits_30", "credits_100"]
    assert packs[0].credits == 1000
    assert packs[0].stars == 1000
    assert manager.get_plan("plus").stars == 250
    assert manager.get_plan("team").seats == 5


def test_code_supplied_plans_win():
    custom = [Plan(plan_id="solo", title="Solo", stars=100, usd_cents=199, minutes_per_period=60)]
    manager = _manager(plans=custom)
    assert [p.plan_id for p in manager.list_plans()] == ["solo"]


@pytest.mark.asyncio
async def test_friend_and_admin_bypass(monkeypatch, manager):
    monkeypatch.setattr("botspot.utils.user_ops.is_admin", lambda user: int(user) == 1)
    monkeypatch.setattr("botspot.utils.user_ops.is_friend", lambda user: int(user) == 2)
    admin_ent = await manager.check_entitlement(1)
    friend_ent = await manager.check_entitlement(2)
    assert admin_ent.source == SOURCE_ADMIN
    assert admin_ent.until is None
    assert friend_ent.source == SOURCE_FRIEND
    admin_dec = await manager.authorize(1, kind="audio", estimated_minutes=10, estimated_cost_usd=1)
    friend_dec = await manager.authorize(
        2, kind="audio", estimated_minutes=10, estimated_cost_usd=1
    )
    assert admin_dec.allowed and admin_dec.source == SOURCE_ADMIN
    assert friend_dec.allowed and friend_dec.source == SOURCE_FRIEND
    assert admin_dec.hold_id is None


@pytest.mark.asyncio
async def test_authorize_order_plan_minutes_then_credits_then_trial(monkeypatch, manager):
    monkeypatch.setattr("botspot.utils.user_ops.is_admin", lambda user: False)
    monkeypatch.setattr("botspot.utils.user_ops.is_friend", lambda user: False)
    user_id = 10
    await manager.grant(user_id, "plus", days=30, granted_by=1)
    sub_dec = await manager.authorize(
        user_id, kind="audio", estimated_minutes=5, estimated_cost_usd=1.0, weight=1.0
    )
    assert sub_dec.allowed and sub_dec.source == SOURCE_SUBSCRIPTION

    await manager.consume_minutes(user_id, 300)
    await manager.accounts.update_one(
        {"_id": user_id}, {"$set": {"balance_credits": 500}}, upsert=True
    )
    await manager._refresh_entitlement(user_id)
    credit_dec = await manager.authorize(
        user_id, kind="audio", estimated_minutes=5, estimated_cost_usd=0.10
    )
    assert credit_dec.allowed and credit_dec.source == SOURCE_CREDITS
    assert credit_dec.hold_id

    empty = _manager()
    trial_dec = await empty.authorize(
        99, kind="audio", estimated_minutes=1, estimated_cost_usd=0.01
    )
    assert trial_dec.allowed and trial_dec.source == SOURCE_TRIAL


@pytest.mark.asyncio
async def test_credits_hold_settle_and_release(monkeypatch, manager):
    monkeypatch.setattr("botspot.utils.user_ops.is_admin", lambda user: False)
    monkeypatch.setattr("botspot.utils.user_ops.is_friend", lambda user: False)
    user_id = 11
    await manager.grant_admin_credits(user_id, 1000, granted_by=1)
    # media 0.25 * 1.6 = 0.40 → 40 credits
    dec = await manager.authorize(
        user_id, kind="audio", estimated_minutes=10, estimated_cost_usd=0.25
    )
    assert dec.source == SOURCE_CREDITS
    bal = await manager.get_balance(user_id)
    assert bal.balance_credits == 960
    await manager.settle(dec.hold_id, actual_cost_usd=0.10, actual_minutes=4)
    bal = await manager.get_balance(user_id)
    assert (
        bal.balance_credits == 990
    )  # 1000 - 40 + 30 unused of actual 10 credits? 0.10*100=10, unused 30
    # 960 + (40-10) = 990

    dec2 = await manager.authorize(
        user_id, kind="audio", estimated_minutes=10, estimated_cost_usd=0.25
    )
    await manager.release(dec2.hold_id)
    bal = await manager.get_balance(user_id)
    assert bal.balance_credits == 990


@pytest.mark.asyncio
async def test_stars_first_payment_and_renewal_idempotent(monkeypatch, manager):
    monkeypatch.setattr("botspot.utils.user_ops.is_admin", lambda user: False)
    monkeypatch.setattr("botspot.utils.user_ops.is_friend", lambda user: False)
    user_id = 12
    link = await manager.create_stars_subscription_link(user_id, "plus")
    assert link.startswith("https://example.com/")
    kwargs = manager.bot().invoice_links[0]
    assert kwargs["subscription_period"] == TELEGRAM_STARS_PERIOD_SECONDS
    assert kwargs["currency"] == "XTR"
    assert kwargs["prices"][0].amount == 250
    payload = kwargs["payload"]
    exp = int(time.time()) + 30 * 86400

    async def pay(charge_id, first=True):
        sp = SimpleNamespace(
            invoice_payload=payload,
            telegram_payment_charge_id=charge_id,
            provider_payment_charge_id=charge_id,
            is_recurring=True,
            is_first_recurring=first,
            subscription_expiration_date=exp,
        )
        return await manager.handle_successful_payment(SimpleNamespace(successful_payment=sp))

    first = await pay("chg_first", first=True)
    again = await pay("chg_first", first=True)
    assert first.source == SOURCE_SUBSCRIPTION
    assert again.source == SOURCE_SUBSCRIPTION
    subs = await manager.list_subscribers()
    assert len(subs) == 1
    renewal = await pay("chg_renew", first=False)
    assert renewal.source == SOURCE_SUBSCRIPTION
    ledger = await manager.get_recent_ledger(user_id, limit=20)
    charge_ids = {row.get("provider_charge_id") for row in ledger}
    assert "telegram_stars:chg_first" in charge_ids or any(
        "chg_first" in str(row.get("_id")) for row in ledger
    )


@pytest.mark.asyncio
async def test_stars_pack_payment_credits_once(monkeypatch, manager):
    monkeypatch.setattr("botspot.utils.user_ops.is_admin", lambda user: False)
    monkeypatch.setattr("botspot.utils.user_ops.is_friend", lambda user: False)
    invoice = await manager.create_stars_invoice(20, "credits_10")
    sp = SimpleNamespace(
        invoice_payload=invoice.payment_payload,
        telegram_payment_charge_id="pack_1",
        provider_payment_charge_id="pack_1",
        is_recurring=False,
        is_first_recurring=False,
        subscription_expiration_date=None,
    )
    await manager.handle_successful_payment(SimpleNamespace(successful_payment=sp))
    await manager.handle_successful_payment(SimpleNamespace(successful_payment=sp))
    bal = await manager.get_balance(20)
    assert bal.balance_credits == 1000


@pytest.mark.asyncio
async def test_expiry_with_grace(monkeypatch, manager):
    monkeypatch.setattr("botspot.utils.user_ops.is_admin", lambda user: False)
    monkeypatch.setattr("botspot.utils.user_ops.is_friend", lambda user: False)
    user_id = 13
    await manager.grant(user_id, "plus", days=30, granted_by=1)
    past = manager._now() - timedelta(days=1)
    await manager.subscriptions.update_one(
        {"user_id": user_id, "status": "active"},
        {"$set": {"current_period_end": past}},
    )
    await manager._refresh_entitlement(user_id)
    ent = await manager.check_entitlement(user_id)
    assert ent.source in {SOURCE_SUBSCRIPTION, "manual"}  # still in 2-day grace

    await manager.subscriptions.update_one(
        {"user_id": user_id, "status": "active"},
        {"$set": {"current_period_end": manager._now() - timedelta(days=3)}},
    )
    await manager.reconcile()
    ent = await manager.check_entitlement(user_id)
    assert ent.source in {SOURCE_TRIAL, SOURCE_NONE}
    expired = await manager.list_subscribers(status="expired")
    assert expired


@pytest.mark.asyncio
async def test_manual_grant_and_revoke(monkeypatch, manager):
    monkeypatch.setattr("botspot.utils.user_ops.is_admin", lambda user: False)
    monkeypatch.setattr("botspot.utils.user_ops.is_friend", lambda user: False)
    sub = await manager.grant(14, "pro", days=7, granted_by=99, note="comp")
    assert sub.provider == "manual"
    assert sub.plan_id == "pro"
    ent = await manager.check_entitlement(14)
    assert ent.source in {SOURCE_SUBSCRIPTION, "manual"}
    assert ent.plan_id == "pro"
    await manager.revoke(14, granted_by=99)
    ent = await manager.check_entitlement(14)
    assert ent.plan_id is None or ent.source in {SOURCE_TRIAL, SOURCE_NONE}


@pytest.mark.asyncio
async def test_stripe_live_key_refusal(manager):
    live = _manager(
        settings=_settings(
            stripe_secret_key=SecretStr("sk_live_not_a_real_key"),
            stripe_allow_live=False,
            public_base_url="https://example.com",
        )
    )
    with pytest.raises(SubscriptionPaymentError) as exc:
        await live.create_stripe_checkout(1, sku="credits_10")
    assert "Live Stripe keys" in str(exc.value.user_message)
    assert live.invoices.docs == {}


def test_stripe_webhook_signature_and_live_allowed():
    manager = _manager(settings=_settings(stripe_webhook_secret=SecretStr("whsec_test")))
    body = json.dumps({"id": "evt_1", "type": "ping"}).encode()
    timestamp = int(time.time())
    expected = hmac.new(b"whsec_test", f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    event = manager.verify_stripe_webhook(body, f"t={timestamp},v1={expected}")
    assert event["id"] == "evt_1"

    allowed = _manager(
        settings=_settings(stripe_secret_key=SecretStr("rk_live_x"), stripe_allow_live=True)
    )
    from botspot.components.new.subscription_manager.stripe import reject_live_stripe_key

    assert reject_live_stripe_key(allowed, "rk_live_x") is None


@pytest.mark.asyncio
async def test_stripe_event_credits_signed_invoice(monkeypatch, manager):
    monkeypatch.setattr("botspot.utils.user_ops.is_admin", lambda user: False)
    monkeypatch.setattr("botspot.utils.user_ops.is_friend", lambda user: False)
    from botspot.components.new.subscription_manager.payloads import sign_invoice_metadata

    user_id = 15
    pack = manager.get_pack("credits_10")
    invoice = await manager._create_invoice(
        provider=PROVIDER_STRIPE,
        user_id=user_id,
        sku=pack.sku,
        title=pack.display_title,
        credits=pack.credits,
        amount_minor=pack.usd_cents,
        currency="USD",
        status="open",
    )
    signature = sign_invoice_metadata(manager.settings, invoice.invoice_id, user_id)
    event = {
        "id": "evt_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_1",
                "payment_status": "paid",
                "metadata": {
                    "invoice_id": invoice.invoice_id,
                    "telegram_user_id": str(user_id),
                    "signature": signature,
                    "kind": "pack",
                },
            }
        },
    }
    first = await manager.handle_stripe_event(event)
    second = await manager.handle_stripe_event(event)
    assert first is True
    assert second is False
    assert (await manager.get_balance(user_id)).balance_credits == 1000


@pytest.mark.asyncio
async def test_stripe_unpaid_completed_does_not_credit(manager):
    from botspot.components.new.subscription_manager.payloads import sign_invoice_metadata

    invoice = await manager._create_invoice(
        provider=PROVIDER_STRIPE,
        user_id=16,
        sku="credits_10",
        title="pack",
        credits=1000,
        amount_minor=1000,
        currency="USD",
        status="open",
    )
    signature = sign_invoice_metadata(manager.settings, invoice.invoice_id, 16)
    event = {
        "id": "evt_unpaid",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_unpaid",
                "payment_status": "unpaid",
                "metadata": {
                    "invoice_id": invoice.invoice_id,
                    "telegram_user_id": "16",
                    "signature": signature,
                },
            }
        },
    }
    assert await manager.handle_stripe_event(event) is False
    assert (await manager.get_balance(16)).balance_credits == 0


@pytest.mark.asyncio
async def test_cancel_and_refund_stars(monkeypatch, manager):
    monkeypatch.setattr("botspot.utils.user_ops.is_admin", lambda user: False)
    monkeypatch.setattr("botspot.utils.user_ops.is_friend", lambda user: False)
    user_id = 17
    await manager._activate_subscription(
        user_id=user_id,
        plan_id="plus",
        provider=PROVIDER_STARS,
        provider_sub_id="chg_c",
        provider_charge_id="chg_c",
        period_end=manager._now() + timedelta(days=20),
    )
    await manager.cancel_subscription(user_id, at_period_end=True)
    assert manager.bot().edits
    assert manager.bot().edits[0]["is_canceled"] is True
    await manager.refund(user_id, "chg_c")
    assert manager.bot().refunds


@pytest.mark.asyncio
async def test_pre_checkout_valid_and_invalid(manager):
    invoice = await manager.create_stars_invoice(18, "credits_10")
    ok_query = MagicMock()
    ok_query.invoice_payload = invoice.payment_payload
    ok_query.answer = AsyncMock()
    await manager.handle_pre_checkout(ok_query)
    ok_query.answer.assert_awaited_with(ok=True)

    bad = MagicMock()
    bad.invoice_payload = "not-a-payload"
    bad.answer = AsyncMock()
    await manager.handle_pre_checkout(bad)
    assert bad.answer.await_args.kwargs["ok"] is False


def test_invoice_payload_compact_and_legacy(manager):
    invoice_id = "a" * 32
    payload = build_invoice_payload(manager.settings, PROVIDER_STARS, invoice_id, 1234567890)
    assert payload.startswith("b:ts:")
    assert len(payload.encode()) <= 128
    parsed = parse_invoice_payload(manager.settings, payload, expected_provider=PROVIDER_STARS)
    assert parsed["telegram_user_id"] == 1234567890
    from botspot.components.new.subscription_manager.payloads import sign_invoice_metadata

    sig = sign_invoice_metadata(manager.settings, invoice_id, 1234567890)
    legacy = f"billing:{PROVIDER_STARS}:{invoice_id}:1234567890:{sig}"
    assert parse_invoice_payload(manager.settings, legacy)["invoice_id"] == invoice_id


@pytest.mark.asyncio
async def test_yookassa_unconfigured_and_ton_unconfigured(manager):
    yk = await manager.create_yookassa_payment(1, "credits_10")
    assert yk.ok is False
    assert "YOOKASSA_SHOP_ID" in (yk.user_message or "")
    ton = await manager.create_ton_manual_invoice(1, "credits_10")
    assert ton.ok is False


@pytest.mark.asyncio
async def test_ton_manual_confirmation_credits_once(manager):
    ton_mgr = _manager(settings=_settings(ton_wallet_address="EQ_TEST_WALLET", ton_usd_rate=5.0))
    result = await ton_mgr.create_ton_manual_invoice(21, "credits_30")
    assert result.ok is True
    first = await ton_mgr.confirm_manual_invoice(result.invoice.invoice_id, admin_user_id=1)
    second = await ton_mgr.confirm_manual_invoice(result.invoice.invoice_id, admin_user_id=1)
    assert first is True
    assert second is False
    assert (await ton_mgr.get_balance(21)).balance_credits == 3000


@pytest.mark.asyncio
async def test_yookassa_create_and_event(monkeypatch):
    mgr = _manager(
        settings=_settings(
            yookassa_shop_id="shop_123",
            yookassa_secret_key=SecretStr("test_secret"),
            yookassa_return_url="https://example.com/return",
            yookassa_usd_rate=90.0,
        )
    )

    async def fake_request(manager, method, path, json_body=None, idempotence_key=None):
        if method == "POST":
            return 200, {
                "id": "pay_1",
                "confirmation": {"confirmation_url": "https://example.com/pay"},
            }
        return 200, {
            "id": "pay_1",
            "status": "succeeded",
            "metadata": json_body or {},
        }

    from botspot.components.new.subscription_manager import yookassa as yk

    monkeypatch.setattr(yk, "yookassa_request", fake_request)
    result = await mgr.create_yookassa_payment(22, "credits_10")
    assert result.ok is True
    assert result.checkout_url == "https://example.com/pay"

    from botspot.components.new.subscription_manager.payloads import sign_invoice_metadata

    invoice_id = result.invoice.invoice_id
    signature = sign_invoice_metadata(mgr.settings, invoice_id, 22)

    async def fake_get(manager, method, path, json_body=None, idempotence_key=None):
        return 200, {
            "id": "pay_1",
            "status": "succeeded",
            "metadata": {
                "invoice_id": invoice_id,
                "telegram_user_id": "22",
                "signature": signature,
            },
        }

    monkeypatch.setattr(yk, "yookassa_request", fake_get)
    first = await mgr.handle_yookassa_event(
        {"event": "payment.succeeded", "object": {"id": "pay_1"}}
    )
    second = await mgr.handle_yookassa_event(
        {"event": "payment.succeeded", "object": {"id": "pay_1"}}
    )
    assert first is True
    assert second is False
    assert (await mgr.get_balance(22)).balance_credits == 1000


@pytest.mark.asyncio
async def test_trial_caps_deny(monkeypatch):
    monkeypatch.setattr("botspot.utils.user_ops.is_admin", lambda user: False)
    monkeypatch.setattr("botspot.utils.user_ops.is_friend", lambda user: False)
    mgr = _manager(
        settings=_settings(trial_user_audio_minutes_total=1.0, trial_global_cost_usd_per_day=10)
    )
    first = await mgr.authorize(30, kind="audio", estimated_minutes=1, estimated_cost_usd=0.01)
    assert first.allowed
    second = await mgr.authorize(30, kind="audio", estimated_minutes=1, estimated_cost_usd=0.01)
    assert second.allowed is False
    assert second.message_key in {
        "trial_audio_minutes_cap",
        "trial_audio_requests_cap",
        "trial_limit_reached",
    }


@pytest.mark.asyncio
async def test_initialize_requires_mongo():
    from botspot.core.botspot_settings import BotspotSettings
    from botspot.core.dependency_manager import DependencyManager
    from botspot.components.new.subscription_manager import initialize
    from botspot.utils.internal import Singleton

    Singleton._instances = {}
    DependencyManager(botspot_settings=BotspotSettings())
    with pytest.raises(ConfigurationError):
        initialize(SubscriptionManagerSettings(enabled=True))
    Singleton._instances = {}


def test_aiohttp_routes_paths():
    routes = aiohttp_routes(_manager())
    paths = [getattr(r, "path", None) or getattr(r, "_path", None) for r in routes]
    assert STRIPE_WEBHOOK_PATH in paths or any(
        "/api/billing/stripe/webhook" in str(r) for r in routes
    )


@pytest.mark.asyncio
async def test_require_plan_blocks_trial(monkeypatch, manager):
    monkeypatch.setattr("botspot.utils.user_ops.is_admin", lambda user: False)
    monkeypatch.setattr("botspot.utils.user_ops.is_friend", lambda user: False)
    from botspot.core.botspot_settings import BotspotSettings
    from botspot.core.dependency_manager import DependencyManager
    from botspot.utils.internal import Singleton

    Singleton._instances = {}
    dm = DependencyManager(botspot_settings=BotspotSettings())
    dm.subscription_manager = manager
    monkeypatch.setattr(
        "botspot.components.new.subscription_manager.handlers.send_safe",
        AsyncMock(),
    )
    called = []

    @require_plan()
    async def handler(message):
        called.append(True)

    msg = SimpleNamespace(
        from_user=SimpleNamespace(id=40),
        chat=SimpleNamespace(id=40),
        answer=AsyncMock(),
    )
    await handler(msg)
    assert called == []
    await manager.grant(40, "plus", days=30, granted_by=1)
    await handler(msg)
    assert called == [True]
    Singleton._instances = {}


@pytest.mark.asyncio
async def test_ensure_indexes(manager):
    await manager.ensure_indexes()
    assert manager.accounts.indexes
    assert manager.ledger.indexes
    assert manager.subscriptions.indexes


@pytest.mark.asyncio
async def test_unknown_pack_and_plan(manager):
    with pytest.raises(SubscriptionValidationError):
        manager.get_pack("nope")
    with pytest.raises(SubscriptionValidationError):
        manager.get_plan("nope")


@pytest.mark.asyncio
async def test_weight_double_counts_subscription_minutes(monkeypatch, manager):
    monkeypatch.setattr("botspot.utils.user_ops.is_admin", lambda user: False)
    monkeypatch.setattr("botspot.utils.user_ops.is_friend", lambda user: False)
    user_id = 41
    await manager.grant(user_id, "plus", days=30, granted_by=1)
    dec = await manager.authorize(
        user_id, kind="audio", estimated_minutes=10, estimated_cost_usd=0, weight=2.0
    )
    assert dec.allowed and dec.source == SOURCE_SUBSCRIPTION
    await manager.settle(dec.hold_id, actual_cost_usd=0, actual_minutes=10)
    left = await manager._minutes_left(user_id)
    assert left is not None
    assert left == pytest.approx(280.0)  # 300 - 10*2? settle uses actual_minutes * hold weight
    # consume_minutes in settle: actual_minutes * hold.weight = 10 * 2 = 20 → 280


def test_public_models_importable():
    assert Plan(plan_id="x", title="X", stars=1, usd_cents=1)
    assert CreditPack(sku="s", credits=1, usd_cents=1, stars=1)
    assert Decision(allowed=True, source="trial")
    assert Entitlement(user_id=1, source="none")
    assert Balance(telegram_user_id=1, balance_credits=0, retail_usd=0, audio_minutes=0)


@pytest.mark.asyncio
async def test_stripe_invoice_paid_renews(monkeypatch, manager):
    monkeypatch.setattr("botspot.utils.user_ops.is_admin", lambda user: False)
    monkeypatch.setattr("botspot.utils.user_ops.is_friend", lambda user: False)
    await manager._activate_subscription(
        user_id=50,
        plan_id="plus",
        provider=PROVIDER_STRIPE,
        provider_sub_id="sub_1",
        provider_charge_id="cs_old",
        period_end=manager._now() + timedelta(days=2),
    )
    end_ts = int((manager._now() + timedelta(days=30)).timestamp())
    event = {
        "id": "evt_inv",
        "type": "invoice.paid",
        "data": {
            "object": {
                "id": "in_1",
                "subscription": "sub_1",
                "lines": {"data": [{"period": {"end": end_ts}}]},
            }
        },
    }
    assert await manager.handle_stripe_event(event) is True
    sub = await manager._active_subscription_doc(50)
    assert sub["current_period_end"] > manager._now() + timedelta(days=20)


@pytest.mark.asyncio
async def test_reconcile_star_transactions_credits_missing(monkeypatch, manager):
    monkeypatch.setattr("botspot.utils.user_ops.is_admin", lambda user: False)
    monkeypatch.setattr("botspot.utils.user_ops.is_friend", lambda user: False)
    invoice = await manager.create_stars_invoice(60, "credits_10")
    tx = SimpleNamespace(
        id="tx_missing",
        source=SimpleNamespace(invoice_payload=invoice.payment_payload),
    )
    manager.bot().star_transactions = SimpleNamespace(transactions=[tx])
    summary = await manager.reconcile()
    assert summary["star_credits"] == 1
    assert (await manager.get_balance(60)).balance_credits == 1000


def _observers(dp):
    from aiogram import Dispatcher

    assert isinstance(dp, Dispatcher)
    return {
        "message": len(dp.message.handlers),
        "callback": len(dp.callback_query.handlers),
        "pre_checkout": len(dp.pre_checkout_query.handlers),
        "startup": len(dp.startup.handlers),
    }


def test_setup_dispatcher_register_commands_false_mounts_only_payments():
    from aiogram import Dispatcher

    from botspot.components.new.subscription_manager import setup_dispatcher

    dp = setup_dispatcher(Dispatcher(), register_commands=False)
    counts = _observers(dp)
    # only successful_payment on message; no commands, no sub: callbacks
    assert counts["message"] == 1
    assert counts["callback"] == 0
    assert counts["pre_checkout"] == 1
    assert counts["startup"] == 1


def test_setup_dispatcher_reads_register_commands_setting(monkeypatch):
    from aiogram import Dispatcher

    from botspot.components.new.subscription_manager import setup_dispatcher
    from botspot.core.botspot_settings import BotspotSettings
    from botspot.core.dependency_manager import DependencyManager

    settings = BotspotSettings(subscription_manager={"register_commands": False})
    deps = DependencyManager(botspot_settings=settings)
    monkeypatch.setattr("botspot.core.dependency_manager.get_dependency_manager", lambda: deps)
    dp = setup_dispatcher(Dispatcher())
    counts = _observers(dp)
    assert counts["message"] == 1 and counts["callback"] == 0

    settings.subscription_manager.register_commands = True
    dp2 = setup_dispatcher(Dispatcher())
    assert _observers(dp2)["callback"] == 1
    assert _observers(dp2)["message"] > 1


def _stripe_settings(**overrides) -> SubscriptionManagerSettings:
    data = {
        "stripe_secret_key": SecretStr("sk_test_placeholder"),
        "public_base_url": "https://example.com",
        "stripe_price_ids_json": '{"plus": "price_test_plus"}',
        "signature_secret": SecretStr("test-secret"),
        "enabled": True,
    }
    data.update(overrides)
    return SubscriptionManagerSettings(**data)


def _stripe_http(monkeypatch, handler):
    from botspot.components.new.subscription_manager import stripe as stripe_mod

    monkeypatch.setattr(stripe_mod, "stripe_request", handler)


def test_stripe_request_headers_optional_idempotency_key():
    from botspot.components.new.subscription_manager.stripe import stripe_request_headers

    plain = stripe_request_headers("sk_test_placeholder")
    assert plain["Stripe-Version"]
    assert "Idempotency-Key" not in plain
    keyed = stripe_request_headers("sk_test_placeholder", idempotency_key="inv_abc")
    assert keyed["Idempotency-Key"] == "inv_abc"


def test_stripe_integration_identifier_is_stable():
    from botspot.components.new.subscription_manager.stripe import stripe_integration_identifier

    manager = _manager(settings=_stripe_settings())
    assert stripe_integration_identifier(manager, "credits") == "botspot-credits"
    assert stripe_integration_identifier(manager, "plan") == "botspot-plan"
    custom = _manager(settings=_stripe_settings(stripe_integration_identifier_prefix="acme"))
    assert stripe_integration_identifier(custom, "credits") == "acme-credits"
    assert stripe_integration_identifier(custom, "plan") == "acme-plan"


def test_stripe_integration_identifier_prefix_env(monkeypatch):
    monkeypatch.setenv("BOTSPOT_SUBSCRIPTION_MANAGER_STRIPE_INTEGRATION_IDENTIFIER_PREFIX", "shop")
    settings = SubscriptionManagerSettings()
    assert settings.stripe_integration_identifier_prefix == "shop"


@pytest.mark.asyncio
async def test_stripe_customer_reused_on_checkout(monkeypatch):
    calls: list[dict] = []

    async def fake_request(manager, method, url, data=None, idempotency_key=None):
        calls.append(
            {"method": method, "url": url, "data": dict(data or {}), "key": idempotency_key}
        )
        if "customers" in url:
            return 200, {"id": "cus_test_1"}
        return 200, {"id": "cs_test_1", "url": "https://checkout.stripe.com/c/pay/cs_test_1"}

    _stripe_http(monkeypatch, fake_request)
    bot = FakeBot()
    bot.usernames[70] = "alice"
    mgr = _manager(settings=_stripe_settings(), bot=bot)

    first = await mgr.create_stripe_checkout(70, sku="credits_10")
    second = await mgr.create_stripe_checkout(70, sku="credits_10")
    assert first.startswith("https://checkout.stripe.com/")
    assert second.startswith("https://checkout.stripe.com/")

    customer_calls = [c for c in calls if "customers" in c["url"]]
    checkout_calls = [c for c in calls if "checkout/sessions" in c["url"]]
    assert len(customer_calls) == 1
    assert customer_calls[0]["key"] == "customer:70"
    assert customer_calls[0]["data"]["metadata[telegram_user_id]"] == "70"
    assert customer_calls[0]["data"]["name"] == "alice"
    assert customer_calls[0]["data"]["description"] == "alice"
    assert "email" not in customer_calls[0]["data"]
    assert len(checkout_calls) == 2
    assert checkout_calls[0]["data"]["customer"] == "cus_test_1"
    assert checkout_calls[1]["data"]["customer"] == "cus_test_1"
    assert checkout_calls[0]["data"]["mode"] == "payment"
    assert checkout_calls[0]["data"]["integration_identifier"] == "botspot-credits"
    invoice_ids = {doc["_id"] for doc in mgr.invoices.docs.values()}
    assert {c["key"] for c in checkout_calls} == invoice_ids
    account = await mgr.accounts.find_one({"_id": 70})
    assert account["stripe_customer_id"] == "cus_test_1"


@pytest.mark.asyncio
async def test_stripe_plan_checkout_passes_customer_and_stable_id(monkeypatch):
    calls: list[dict] = []

    async def fake_request(manager, method, url, data=None, idempotency_key=None):
        calls.append({"url": url, "data": dict(data or {}), "key": idempotency_key})
        if "customers" in url:
            return 200, {"id": "cus_plan_1"}
        return 200, {"id": "cs_plan_1", "url": "https://checkout.stripe.com/c/pay/cs_plan_1"}

    _stripe_http(monkeypatch, fake_request)
    mgr = _manager(settings=_stripe_settings())
    url = await mgr.create_stripe_checkout(71, plan_id="plus")
    assert url
    checkout = [c for c in calls if "checkout/sessions" in c["url"]][0]
    assert checkout["data"]["mode"] == "subscription"
    assert checkout["data"]["customer"] == "cus_plan_1"
    assert checkout["data"]["integration_identifier"] == "botspot-plan"
    assert checkout["data"]["line_items[0][price]"] == "price_test_plus"
    assert checkout["key"]


@pytest.mark.asyncio
async def test_create_stripe_portal_url(monkeypatch):
    mgr = _manager(settings=_stripe_settings())
    with pytest.raises(SubscriptionPaymentError) as exc:
        await mgr.create_stripe_portal_url(72)
    assert "No Stripe customer" in str(exc.value.user_message)

    await mgr.accounts.update_one(
        {"_id": 72}, {"$set": {"stripe_customer_id": "cus_portal_1"}}, upsert=True
    )
    calls: list[dict] = []

    async def fake_request(manager, method, url, data=None, idempotency_key=None):
        calls.append({"url": url, "data": dict(data or {})})
        return 200, {"url": "https://billing.stripe.com/p/session/test"}

    _stripe_http(monkeypatch, fake_request)
    url = await mgr.create_stripe_portal_url(72)
    assert url == "https://billing.stripe.com/p/session/test"
    assert calls[0]["data"]["customer"] == "cus_portal_1"
    assert calls[0]["data"]["return_url"] == "https://example.com/billing/success"


@pytest.mark.asyncio
async def test_stripe_invoice_payment_failed_marks_past_due(monkeypatch):
    mgr = _manager(settings=_stripe_settings())
    await mgr._activate_subscription(
        user_id=73,
        plan_id="plus",
        provider=PROVIDER_STRIPE,
        provider_sub_id="sub_fail_1",
        provider_charge_id="cs_old",
        period_end=mgr._now() + timedelta(days=20),
    )
    await mgr.accounts.update_one(
        {"_id": 73}, {"$set": {"stripe_customer_id": "cus_fail_1"}}, upsert=True
    )

    async def fake_request(manager, method, url, data=None, idempotency_key=None):
        return 200, {"url": "https://billing.stripe.com/p/session/fail"}

    _stripe_http(monkeypatch, fake_request)
    event = {
        "id": "evt_fail_1",
        "type": "invoice.payment_failed",
        "data": {
            "object": {
                "id": "in_fail_1",
                "subscription": "sub_fail_1",
            }
        },
    }
    assert await mgr.handle_stripe_event(event) is True
    sub = await mgr.subscriptions.find_one({"provider_sub_id": "sub_fail_1"})
    assert sub["status"] == "past_due"
    assert mgr.bot().messages
    assert "https://billing.stripe.com/p/session/fail" in mgr.bot().messages[0]["text"]
    assert mgr.bot().messages[0]["chat_id"] == 73

    replay = await mgr.handle_stripe_event(event)
    assert replay is False
    assert len(mgr.bot().messages) == 1


@pytest.mark.asyncio
async def test_stripe_invoice_payment_failed_parent_subscription_no_notice_without_customer():
    mgr = _manager(settings=_stripe_settings())
    await mgr._activate_subscription(
        user_id=74,
        plan_id="plus",
        provider=PROVIDER_STRIPE,
        provider_sub_id="sub_fail_2",
        provider_charge_id="cs_old_2",
        period_end=mgr._now() + timedelta(days=20),
    )
    event = {
        "id": "evt_fail_parent",
        "type": "invoice.payment_failed",
        "data": {
            "object": {
                "id": "in_fail_2",
                "parent": {
                    "type": "subscription_details",
                    "subscription_details": {"subscription": "sub_fail_2"},
                },
            }
        },
    }
    assert await mgr.handle_stripe_event(event) is True
    sub = await mgr.subscriptions.find_one({"provider_sub_id": "sub_fail_2"})
    assert sub["status"] == "past_due"
    assert mgr.bot().messages == []


@pytest.mark.asyncio
async def test_stripe_replayed_event_returns_false_before_fulfill(monkeypatch, manager):
    from botspot.components.new.subscription_manager import stripe as stripe_mod
    from botspot.components.new.subscription_manager.payloads import sign_invoice_metadata

    fulfilled: list[str] = []
    original = stripe_mod._fulfill_stripe_session

    async def tracking_fulfill(*args, **kwargs):
        fulfilled.append("yes")
        return await original(*args, **kwargs)

    monkeypatch.setattr(stripe_mod, "_fulfill_stripe_session", tracking_fulfill)
    invoice = await manager._create_invoice(
        provider=PROVIDER_STRIPE,
        user_id=75,
        sku="credits_10",
        title="pack",
        credits=1000,
        amount_minor=1000,
        currency="USD",
        status="open",
    )
    signature = sign_invoice_metadata(manager.settings, invoice.invoice_id, 75)
    event = {
        "id": "evt_replay_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_replay_1",
                "payment_status": "paid",
                "metadata": {
                    "invoice_id": invoice.invoice_id,
                    "telegram_user_id": "75",
                    "signature": signature,
                    "kind": "pack",
                },
            }
        },
    }
    assert await manager.handle_stripe_event(event) is True
    assert await manager.handle_stripe_event(event) is False
    assert fulfilled == ["yes"]


@pytest.mark.asyncio
async def test_stripe_invoice_paid_replay_still_processes(monkeypatch, manager):
    monkeypatch.setattr("botspot.utils.user_ops.is_admin", lambda user: False)
    monkeypatch.setattr("botspot.utils.user_ops.is_friend", lambda user: False)
    await manager._activate_subscription(
        user_id=76,
        plan_id="plus",
        provider=PROVIDER_STRIPE,
        provider_sub_id="sub_replay_paid",
        provider_charge_id="cs_old_r",
        period_end=manager._now() + timedelta(days=2),
    )
    end_ts = int((manager._now() + timedelta(days=30)).timestamp())
    event = {
        "id": "evt_paid_replay",
        "type": "invoice.paid",
        "data": {
            "object": {
                "id": "in_replay",
                "subscription": "sub_replay_paid",
                "lines": {"data": [{"period": {"end": end_ts}}]},
            }
        },
    }
    assert await manager.handle_stripe_event(event) is True
    assert await manager.handle_stripe_event(event) is True
    sub = await manager._active_subscription_doc(76)
    assert sub["current_period_end"] > manager._now() + timedelta(days=20)
