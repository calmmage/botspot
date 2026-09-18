"""Stripe Checkout adapter (whisper port + subscription mode)."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import string
import time
from typing import TYPE_CHECKING, Any, Optional

import aiohttp

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
    STRIPE_CANCEL_EVENT_TYPES,
    STRIPE_CHECKOUT_SESSIONS_URL,
    STRIPE_FAIL_EVENT_TYPES,
    STRIPE_FULFILL_EVENT_TYPES,
    STRIPE_PAID_STATUSES,
    STRIPE_RENEW_EVENT_TYPES,
)
from botspot.core.errors import SubscriptionPaymentError, SubscriptionValidationError
from botspot.utils.internal import get_logger

if TYPE_CHECKING:
    from botspot.components.new.subscription_manager.manager import SubscriptionManager
    from botspot.components.new.subscription_manager.models import CreditPack, Plan

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


def stripe_request_headers(secret_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {secret_key}",
        "Stripe-Version": STRIPE_API_VERSION,
    }


def with_checkout_session_placeholder(success_url: str) -> str:
    if "{CHECKOUT_SESSION_ID}" in success_url:
        return success_url
    separator = "&" if "?" in success_url else "?"
    return f"{success_url}{separator}session_id={{CHECKOUT_SESSION_ID}}"


def stripe_integration_identifier(prefix: str) -> str:
    suffix = "".join(secrets.choice(string.ascii_lowercase) for _ in range(8))
    return f"{prefix}-{suffix}"


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
        "integration_identifier": stripe_integration_identifier("botspot-credits"),
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
        "integration_identifier": stripe_integration_identifier("botspot-plan"),
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


async def create_stripe_checkout(
    manager: SubscriptionManager,
    user_id: int,
    *,
    sku: str | None = None,
    plan_id: str | None = None,
) -> str:
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
    elif sku:
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
    else:
        raise SubscriptionValidationError("sku or plan_id is required.")

    async with aiohttp.ClientSession() as session:
        async with session.post(
            STRIPE_CHECKOUT_SESSIONS_URL,
            data=form,
            headers=stripe_request_headers(secret_key),
            timeout=aiohttp.ClientTimeout(total=20),
        ) as response:
            body_text = await response.text()
            if response.status >= 300:
                await manager._fail_invoice(invoice.invoice_id, body_text)
                logger.warning(
                    f"Stripe checkout failed for invoice {invoice.invoice_id}: "
                    f"{response.status} {body_text}"
                )
                raise SubscriptionPaymentError(
                    "Stripe checkout failed.",
                    user_message="Stripe checkout failed. Please try again later.",
                )
            payload = json.loads(body_text)

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


async def handle_stripe_event(manager: SubscriptionManager, event: dict[str, Any]) -> bool:
    event_type = str(event.get("type") or "")
    event_id = str(event.get("id") or "")
    if event_id:
        is_new = await manager._record_webhook_event(PROVIDER_STRIPE, event_id)
        if not is_new and event_type not in STRIPE_RENEW_EVENT_TYPES:
            # still fulfill via charge-id uniqueness
            pass

    obj = (event.get("data") or {}).get("object") or {}
    if event_type in STRIPE_FAIL_EVENT_TYPES:
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
    sub_id = str(invoice_obj.get("subscription") or "")
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


def _period_end_from_stripe_invoice(invoice_obj: dict[str, Any]):
    from datetime import datetime, timezone

    lines = (invoice_obj.get("lines") or {}).get("data") or []
    if lines:
        end_ts = (lines[0].get("period") or {}).get("end")
        if end_ts:
            return datetime.fromtimestamp(int(end_ts), tz=timezone.utc).replace(tzinfo=None)
    return None
