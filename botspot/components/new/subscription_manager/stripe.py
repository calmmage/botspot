"""Stripe Checkout adapter (whisper port + subscription mode)."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import TYPE_CHECKING, Any, Optional

import aiohttp

from botspot.components.middlewares.i18n import t
from botspot.components.new.subscription_manager.payloads import (
    secret_to_str,
    sign_invoice_metadata,
    verify_invoice_metadata,
)
from botspot.components.new.subscription_manager.settings import (
    KIND_PACK,
    KIND_SUBSCRIPTION,
    PROVIDER_STRIPE,
    STATUS_FAILED,
    STATUS_OPEN,
    STATUS_PENDING,
    STRIPE_API_VERSION,
    STRIPE_BILLING_PORTAL_SESSIONS_URL,
    STRIPE_CANCEL_EVENT_TYPES,
    STRIPE_CHECKOUT_SESSIONS_URL,
    STRIPE_CUSTOMERS_URL,
    STRIPE_FAIL_EVENT_TYPES,
    STRIPE_FULFILL_EVENT_TYPES,
    STRIPE_PAID_STATUSES,
    STRIPE_RENEW_EVENT_TYPES,
    SUB_PAST_DUE,
)
from botspot.core.errors import SubscriptionPaymentError, SubscriptionValidationError
from botspot.utils.internal import get_logger

if TYPE_CHECKING:
    from botspot.components.new.subscription_manager.manager import SubscriptionManager
    from botspot.components.new.subscription_manager.models import CreditPack, Invoice, Plan

logger = get_logger()


def reject_live_stripe_key(manager: SubscriptionManager, secret_key: str) -> Optional[str]:
    live_key = secret_key.startswith(("sk_live_", "rk_live_"))
    if live_key and not manager.settings.stripe_allow_live:
        return (
            "Live Stripe keys are blocked in this process. Set "
            "BOTSPOT_SUBSCRIPTION_MANAGER_STRIPE_ALLOW_LIVE=true after the webhook "
            "and public HTTPS URL are live. Until then use a sandbox restricted key "
            "(rk_test_...)."
        )
    return None


def stripe_price_ids(manager: SubscriptionManager) -> dict[str, str]:
    raw = manager.settings.stripe_price_ids_json.strip()
    if not raw:
        return {}
    parsed = json.loads(raw)
    return {str(k): str(v) for k, v in parsed.items()}


def stripe_price_id(manager: SubscriptionManager, key: str) -> str:
    return stripe_price_ids(manager).get(key, "")


def stripe_return_urls(manager: SubscriptionManager) -> tuple[str, str]:
    base = manager.settings.public_base_url.rstrip("/")
    success = f"{base}/billing/success" if base else ""
    cancel = f"{base}/billing/cancel" if base else ""
    return success, cancel


def stripe_request_headers(secret_key: str, idempotency_key: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {secret_key}",
        "Stripe-Version": STRIPE_API_VERSION,
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def with_checkout_session_placeholder(success_url: str) -> str:
    if "{CHECKOUT_SESSION_ID}" in success_url:
        return success_url
    separator = "&" if "?" in success_url else "?"
    return f"{success_url}{separator}session_id={{CHECKOUT_SESSION_ID}}"


def stripe_integration_identifier(manager: SubscriptionManager, kind: str) -> str:
    prefix = (manager.settings.stripe_integration_identifier_prefix or "botspot").strip()
    prefix = prefix.rstrip("-") or "botspot"
    return f"{prefix}-{kind}"


def parse_stripe_signature(signature_header: str) -> tuple[int, list[str]]:
    timestamp = None
    signatures: list[str] = []
    for item in signature_header.split(","):
        key, _, value = item.partition("=")
        if key == "t":
            timestamp = int(value)
        elif key == "v1":
            signatures.append(value)
    if timestamp is None or not signatures:
        raise SubscriptionValidationError("Malformed Stripe-Signature header.")
    return timestamp, signatures


def verify_stripe_webhook(
    manager: SubscriptionManager, raw_body: bytes, signature_header: str
) -> dict:
    secret = secret_to_str(manager.settings.stripe_webhook_secret)
    if not secret:
        raise SubscriptionValidationError("Stripe webhook secret is not configured.")
    timestamp, signatures = parse_stripe_signature(signature_header)
    if abs(int(time.time()) - timestamp) > 300:
        raise SubscriptionValidationError("Stripe webhook timestamp is outside tolerance.")
    signed_payload = f"{timestamp}.".encode() + raw_body
    expected = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, sig) for sig in signatures):
        raise SubscriptionValidationError("Invalid Stripe webhook signature.")
    return json.loads(raw_body.decode("utf-8"))


def _require_stripe_secret(manager: SubscriptionManager) -> str:
    secret_key = secret_to_str(manager.settings.stripe_secret_key)
    success_url, cancel_url = stripe_return_urls(manager)
    if not secret_key or not success_url or not cancel_url:
        raise SubscriptionPaymentError(
            "Stripe is not configured.",
            user_message=(
                "Stripe is not configured. Set BOTSPOT_SUBSCRIPTION_MANAGER_STRIPE_SECRET_KEY "
                "and BOTSPOT_SUBSCRIPTION_MANAGER_PUBLIC_BASE_URL."
            ),
        )
    live_key_message = reject_live_stripe_key(manager, secret_key)
    if live_key_message:
        raise SubscriptionPaymentError(live_key_message, user_message=live_key_message)
    return secret_key


async def stripe_request(
    manager: SubscriptionManager,
    method: str,
    url: str,
    data: dict[str, str] | None = None,
    idempotency_key: str | None = None,
) -> tuple[int, dict[str, Any]]:
    secret_key = secret_to_str(manager.settings.stripe_secret_key)
    headers = stripe_request_headers(secret_key, idempotency_key=idempotency_key)
    async with aiohttp.ClientSession() as session:
        async with session.request(
            method,
            url,
            data=data,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as response:
            body_text = await response.text()
            if not body_text:
                return response.status, {}
            try:
                return response.status, json.loads(body_text)
            except json.JSONDecodeError:
                return response.status, {"raw": body_text}


def build_pack_checkout_form(
    manager: SubscriptionManager,
    *,
    invoice_id: str,
    telegram_user_id: int,
    signature: str,
    pack: CreditPack,
    success_url: str,
    cancel_url: str,
) -> dict[str, str]:
    form = {
        "mode": "payment",
        "success_url": with_checkout_session_placeholder(success_url),
        "cancel_url": cancel_url,
        "client_reference_id": invoice_id,
        "integration_identifier": stripe_integration_identifier(manager, "credits"),
        "metadata[invoice_id]": invoice_id,
        "metadata[telegram_user_id]": str(telegram_user_id),
        "metadata[sku]": pack.sku,
        "metadata[kind]": KIND_PACK,
        "metadata[signature]": signature,
        "line_items[0][quantity]": "1",
    }
    price_id = pack.stripe_price_id or stripe_price_id(manager, pack.sku)
    if price_id:
        form["line_items[0][price]"] = price_id
    else:
        form["line_items[0][price_data][currency]"] = "usd"
        form["line_items[0][price_data][unit_amount]"] = str(pack.usd_cents)
        form["line_items[0][price_data][product_data][name]"] = pack.display_title
    return form


def build_plan_checkout_form(
    manager: SubscriptionManager,
    *,
    invoice_id: str,
    telegram_user_id: int,
    signature: str,
    plan: Plan,
    success_url: str,
    cancel_url: str,
) -> dict[str, str]:
    price_id = plan.stripe_price_id or stripe_price_id(manager, plan.plan_id)
    if not price_id:
        raise SubscriptionPaymentError(
            "Stripe plan checkout needs a price id.",
            user_message="Stripe subscription price is not configured.",
        )
    return {
        "mode": "subscription",
        "success_url": with_checkout_session_placeholder(success_url),
        "cancel_url": cancel_url,
        "client_reference_id": invoice_id,
        "integration_identifier": stripe_integration_identifier(manager, "plan"),
        "metadata[invoice_id]": invoice_id,
        "metadata[telegram_user_id]": str(telegram_user_id),
        "metadata[plan_id]": plan.plan_id,
        "metadata[kind]": KIND_SUBSCRIPTION,
        "metadata[signature]": signature,
        "line_items[0][quantity]": "1",
        "line_items[0][price]": price_id,
        "subscription_data[metadata][telegram_user_id]": str(telegram_user_id),
        "subscription_data[metadata][plan_id]": plan.plan_id,
        "subscription_data[metadata][invoice_id]": invoice_id,
        "subscription_data[metadata][signature]": signature,
    }


def stored_stripe_customer_id(account: dict[str, Any] | None) -> str:
    return str((account or {}).get("stripe_customer_id") or "")


async def load_stripe_customer_id(manager: SubscriptionManager, user_id: int) -> str:
    doc = await manager.accounts.find_one({"_id": int(user_id)})
    return stored_stripe_customer_id(doc)


async def store_stripe_customer_id(
    manager: SubscriptionManager, user_id: int, customer_id: str
) -> None:
    now = manager._now()
    await manager.accounts.update_one(
        {"_id": int(user_id)},
        {
            "$set": {"stripe_customer_id": customer_id, "updated_at": now},
            "$setOnInsert": {
                "telegram_user_id": int(user_id),
                "balance_credits": 0,
                "status": "active",
                "created_at": now,
            },
        },
        upsert=True,
    )


async def _telegram_username(manager: SubscriptionManager, user_id: int) -> str:
    doc = await manager.accounts.find_one({"_id": int(user_id)})
    if doc and doc.get("username"):
        return str(doc["username"])
    get_chat = getattr(manager._bot, "get_chat", None) if manager._bot is not None else None
    if get_chat is None:
        return ""
    chat = await get_chat(int(user_id))
    username = getattr(chat, "username", None)
    return str(username) if username else ""


async def ensure_stripe_customer(manager: SubscriptionManager, user_id: int) -> str:
    existing = await load_stripe_customer_id(manager, user_id)
    if existing:
        return existing
    form: dict[str, str] = {"metadata[telegram_user_id]": str(int(user_id))}
    username = await _telegram_username(manager, user_id)
    if username:
        form["name"] = username
        form["description"] = username
    status, payload = await stripe_request(
        manager,
        "POST",
        STRIPE_CUSTOMERS_URL,
        data=form,
        idempotency_key=f"customer:{int(user_id)}",
    )
    customer_id = str(payload.get("id") or "")
    if status >= 300 or not customer_id:
        logger.warning(f"Stripe customer create failed for user {user_id}: {status}")
        raise SubscriptionPaymentError(
            "Stripe customer creation failed.",
            user_message="Stripe customer creation failed. Please try again later.",
        )
    await store_stripe_customer_id(manager, user_id, customer_id)
    return customer_id


async def create_stripe_portal_url(manager: SubscriptionManager, user_id: int) -> str:
    _require_stripe_secret(manager)
    success_url, _cancel_url = stripe_return_urls(manager)
    customer_id = await load_stripe_customer_id(manager, user_id)
    if not customer_id:
        raise SubscriptionPaymentError(
            "No Stripe customer for this user.",
            user_message="No Stripe customer yet. Complete a Stripe checkout first, then use /manage.",
        )
    status, payload = await stripe_request(
        manager,
        "POST",
        STRIPE_BILLING_PORTAL_SESSIONS_URL,
        data={"customer": customer_id, "return_url": success_url},
    )
    url = str(payload.get("url") or "")
    if status >= 300 or not url:
        logger.warning(f"Stripe portal session failed for user {user_id}: {status}")
        raise SubscriptionPaymentError(
            "Stripe portal session failed.",
            user_message="Could not open the billing portal. Please try again later.",
        )
    return url


async def _prepare_checkout(
    manager: SubscriptionManager,
    user_id: int,
    *,
    sku: str | None,
    plan_id: str | None,
    success_url: str,
    cancel_url: str,
) -> tuple[Invoice, dict[str, str]]:
    if plan_id:
        plan = manager.get_plan(plan_id)
        invoice = await manager._create_invoice(
            provider=PROVIDER_STRIPE,
            user_id=user_id,
            sku=plan.plan_id,
            title=plan.title,
            credits=int(plan.credits_per_period or 0),
            amount_minor=plan.usd_cents,
            currency="USD",
            status=STATUS_PENDING,
            kind=KIND_SUBSCRIPTION,
            plan_id=plan.plan_id,
        )
        signature = sign_invoice_metadata(manager.settings, invoice.invoice_id, user_id)
        form = build_plan_checkout_form(
            manager,
            invoice_id=invoice.invoice_id,
            telegram_user_id=user_id,
            signature=signature,
            plan=plan,
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return invoice, form
    if sku:
        pack = manager.get_pack(sku)
        invoice = await manager._create_invoice(
            provider=PROVIDER_STRIPE,
            user_id=user_id,
            sku=pack.sku,
            title=pack.display_title,
            credits=pack.credits,
            amount_minor=pack.usd_cents,
            currency="USD",
            status=STATUS_PENDING,
            kind=KIND_PACK,
        )
        signature = sign_invoice_metadata(manager.settings, invoice.invoice_id, user_id)
        form = build_pack_checkout_form(
            manager,
            invoice_id=invoice.invoice_id,
            telegram_user_id=user_id,
            signature=signature,
            pack=pack,
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return invoice, form
    raise SubscriptionValidationError("sku or plan_id is required.")


async def _finalize_checkout(
    manager: SubscriptionManager, invoice: Invoice, status: int, payload: dict[str, Any]
) -> str:
    if status >= 300:
        await manager._fail_invoice(invoice.invoice_id, json.dumps(payload))
        logger.warning(f"Stripe checkout failed for invoice {invoice.invoice_id}: {status}")
        raise SubscriptionPaymentError(
            "Stripe checkout failed.",
            user_message="Stripe checkout failed. Please try again later.",
        )
    checkout_url = payload.get("url")
    if not checkout_url:
        await manager._fail_invoice(invoice.invoice_id, json.dumps(payload))
        raise SubscriptionPaymentError(
            "Stripe did not return a checkout URL.",
            user_message="Stripe did not return a checkout URL.",
        )
    await manager.invoices.update_one(
        {"_id": invoice.invoice_id},
        {
            "$set": {
                "status": STATUS_OPEN,
                "checkout_url": checkout_url,
                "stripe_session_id": payload.get("id"),
                "provider_response": payload,
                "updated_at": manager._now(),
            }
        },
    )
    return checkout_url


async def create_stripe_checkout(
    manager: SubscriptionManager,
    user_id: int,
    *,
    sku: str | None = None,
    plan_id: str | None = None,
) -> str:
    _require_stripe_secret(manager)
    success_url, cancel_url = stripe_return_urls(manager)
    invoice, form = await _prepare_checkout(
        manager, user_id, sku=sku, plan_id=plan_id, success_url=success_url, cancel_url=cancel_url
    )
    form["customer"] = await ensure_stripe_customer(manager, user_id)
    status, payload = await stripe_request(
        manager,
        "POST",
        STRIPE_CHECKOUT_SESSIONS_URL,
        data=form,
        idempotency_key=invoice.invoice_id,
    )
    return await _finalize_checkout(manager, invoice, status, payload)


async def handle_stripe_event(manager: SubscriptionManager, event: dict[str, Any]) -> bool:
    event_type = str(event.get("type") or "")
    event_id = str(event.get("id") or "")
    if event_id:
        is_new = await manager._record_webhook_event(PROVIDER_STRIPE, event_id)
        if not is_new and event_type not in STRIPE_RENEW_EVENT_TYPES:
            return False

    obj = (event.get("data") or {}).get("object") or {}
    if event_type in STRIPE_FAIL_EVENT_TYPES:
        if event_type == "invoice.payment_failed":
            return await _mark_stripe_subscription_past_due(manager, obj)
        return await _mark_stripe_invoice_failed(manager, obj)
    if event_type in STRIPE_CANCEL_EVENT_TYPES:
        return await _cancel_stripe_subscription(manager, obj)
    if event_type in STRIPE_RENEW_EVENT_TYPES:
        return await _renew_stripe_subscription(manager, obj)
    if event_type not in STRIPE_FULFILL_EVENT_TYPES:
        return False
    if obj.get("payment_status") not in STRIPE_PAID_STATUSES:
        return False
    return await _fulfill_stripe_session(manager, obj, event_type)


def _expandable_id(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("id") or "")
    return str(value or "")


def subscription_id_from_invoice(invoice_obj: dict[str, Any]) -> str:
    sub_id = _expandable_id(invoice_obj.get("subscription"))
    if sub_id:
        return sub_id
    parent = invoice_obj.get("parent") or {}
    details = parent.get("subscription_details") or {}
    return _expandable_id(details.get("subscription"))


async def _fulfill_stripe_session(
    manager: SubscriptionManager, session: dict[str, Any], event_type: str
) -> bool:
    metadata = session.get("metadata") or {}
    invoice_id = str(metadata.get("invoice_id") or "")
    telegram_user_id = int(metadata.get("telegram_user_id") or 0)
    signature = str(metadata.get("signature") or "")
    if not invoice_id or not telegram_user_id:
        raise SubscriptionValidationError("Stripe session is missing invoice metadata.")
    if not verify_invoice_metadata(manager.settings, invoice_id, telegram_user_id, signature):
        raise SubscriptionValidationError("Stripe invoice metadata signature is invalid.")
    invoice = await manager.invoices.find_one(
        {"_id": invoice_id, "telegram_user_id": telegram_user_id, "provider": PROVIDER_STRIPE}
    )
    if not invoice:
        raise SubscriptionValidationError(f"Stripe invoice not found: {invoice_id}")

    session_id = str(session.get("id") or invoice_id)
    customer_id = _expandable_id(session.get("customer"))
    if customer_id:
        await store_stripe_customer_id(manager, telegram_user_id, customer_id)
    kind = str(invoice.get("kind") or metadata.get("kind") or KIND_PACK)
    if kind == KIND_SUBSCRIPTION or session.get("mode") == "subscription":
        plan_id = str(invoice.get("plan_id") or metadata.get("plan_id") or "")
        sub_id = str(session.get("subscription") or session_id)
        await manager._activate_subscription(
            user_id=telegram_user_id,
            plan_id=plan_id,
            provider=PROVIDER_STRIPE,
            provider_sub_id=sub_id,
            provider_charge_id=session_id,
            period_end=None,
        )
        credited = True
    else:
        credited = await manager._grant_invoice_credits(
            invoice=invoice,
            provider_event_id=f"stripe:{session_id}",
            metadata={"stripe_session": session, "stripe_event_type": event_type},
        )
    now = manager._now()
    await manager.invoices.update_one(
        {"_id": invoice_id},
        {
            "$set": {
                "status": "paid",
                "paid_at": now,
                "stripe_session_id": session.get("id"),
                "stripe_payment_intent": session.get("payment_intent"),
                "updated_at": now,
            }
        },
    )
    return credited


async def _renew_stripe_subscription(
    manager: SubscriptionManager, invoice_obj: dict[str, Any]
) -> bool:
    sub_id = subscription_id_from_invoice(invoice_obj)
    if not sub_id:
        return False
    period_end = _period_end_from_stripe_invoice(invoice_obj)
    charge_id = str(invoice_obj.get("id") or sub_id)
    return await manager._renew_subscription_by_provider_sub(
        provider=PROVIDER_STRIPE,
        provider_sub_id=sub_id,
        provider_charge_id=charge_id,
        period_end=period_end,
    )


async def _cancel_stripe_subscription(
    manager: SubscriptionManager, sub_obj: dict[str, Any]
) -> bool:
    sub_id = str(sub_obj.get("id") or "")
    if not sub_id:
        return False
    return await manager._cancel_by_provider_sub(PROVIDER_STRIPE, sub_id)


async def _mark_stripe_invoice_failed(
    manager: SubscriptionManager, session: dict[str, Any]
) -> bool:
    metadata = session.get("metadata") or {}
    invoice_id = str(metadata.get("invoice_id") or "")
    if not invoice_id:
        return False
    invoice = await manager.invoices.find_one({"_id": invoice_id, "provider": PROVIDER_STRIPE})
    if not invoice or invoice.get("status") == "paid":
        return False
    now = manager._now()
    await manager.invoices.update_one(
        {"_id": invoice_id},
        {
            "$set": {
                "status": STATUS_FAILED,
                "stripe_session_id": session.get("id"),
                "updated_at": now,
            }
        },
    )
    return False


async def _notify_payment_failed(manager: SubscriptionManager, user_id: int) -> None:
    if not await load_stripe_customer_id(manager, user_id):
        return
    url = await create_stripe_portal_url(manager, user_id)
    await manager.bot().send_message(int(user_id), t("stripe_payment_failed", url=url))


async def _mark_stripe_subscription_past_due(
    manager: SubscriptionManager, invoice_obj: dict[str, Any]
) -> bool:
    sub_id = subscription_id_from_invoice(invoice_obj)
    if not sub_id:
        return False
    sub = await manager.subscriptions.find_one(
        {"provider": PROVIDER_STRIPE, "provider_sub_id": sub_id}
    )
    if not sub:
        return False
    now = manager._now()
    await manager.subscriptions.update_one(
        {"_id": sub["_id"]},
        {"$set": {"status": SUB_PAST_DUE, "updated_at": now}},
    )
    await manager._refresh_entitlement(int(sub["user_id"]))
    await _notify_payment_failed(manager, int(sub["user_id"]))
    return True


def _period_end_from_stripe_invoice(invoice_obj: dict[str, Any]):
    from datetime import datetime, timezone

    lines = (invoice_obj.get("lines") or {}).get("data") or []
    if lines:
        end_ts = (lines[0].get("period") or {}).get("end")
        if end_ts:
            return datetime.fromtimestamp(int(end_ts), tz=timezone.utc).replace(tzinfo=None)
    return None
