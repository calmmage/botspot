"""YooKassa adapter (whisper port). Webhook body is unauthenticated; GET to reconcile."""

from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING, Any, Optional

import aiohttp

from botspot.components.new.subscription_manager.payloads import (
    secret_to_str,
    sign_invoice_metadata,
    verify_invoice_metadata,
)
from botspot.components.new.subscription_manager.settings import (
    KIND_PACK,
    PROVIDER_YOOKASSA,
    STATUS_OPEN,
    STATUS_PENDING,
    YOOKASSA_API_BASE,
)
from botspot.components.new.subscription_manager.models import CheckoutResult
from botspot.core.errors import SubscriptionPaymentError, SubscriptionValidationError
from botspot.utils.internal import get_logger

if TYPE_CHECKING:
    from botspot.components.new.subscription_manager.manager import SubscriptionManager
    from botspot.components.new.subscription_manager.models import CreditPack

logger = get_logger()


def _format_rub(value: Any) -> str:
    return f"{float(value):.2f}"


def yookassa_amount_for_pack(manager: SubscriptionManager, pack: CreditPack) -> Optional[str]:
    usd_rate = float(manager.settings.yookassa_usd_rate or 0.0)
    if usd_rate <= 0:
        return None
    return _format_rub(pack.usd_amount * usd_rate)


def yookassa_return_url(manager: SubscriptionManager) -> str:
    if manager.settings.yookassa_return_url:
        return manager.settings.yookassa_return_url
    base = manager.settings.public_base_url.rstrip("/")
    return f"{base}/billing/yookassa/return" if base else ""


async def yookassa_request(
    manager: SubscriptionManager,
    method: str,
    path: str,
    json_body: Optional[dict[str, Any]] = None,
    idempotence_key: Optional[str] = None,
) -> tuple[int, dict[str, Any]]:
    shop_id = manager.settings.yookassa_shop_id
    secret_key = secret_to_str(manager.settings.yookassa_secret_key)
    token = base64.b64encode(f"{shop_id}:{secret_key}".encode()).decode()
    headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}
    if idempotence_key:
        headers["Idempotence-Key"] = idempotence_key
    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                f"{YOOKASSA_API_BASE}{path}",
                json=json_body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as response:
                text = await response.text()
                return response.status, (json.loads(text) if text else {})
    except aiohttp.ClientError as e:
        raise SubscriptionPaymentError(f"YooKassa request failed: {e}") from e


async def create_yookassa_payment(
    manager: SubscriptionManager, user_id: int, sku: str
) -> CheckoutResult:
    shop_id = manager.settings.yookassa_shop_id
    secret_key = secret_to_str(manager.settings.yookassa_secret_key)
    return_url = yookassa_return_url(manager)
    if not shop_id or not secret_key or not return_url:
        return CheckoutResult(
            ok=False,
            user_message=(
                "YooKassa is not configured. Set BOTSPOT_SUBSCRIPTION_MANAGER_YOOKASSA_SHOP_ID, "
                "BOTSPOT_SUBSCRIPTION_MANAGER_YOOKASSA_SECRET_KEY, and "
                "BOTSPOT_SUBSCRIPTION_MANAGER_YOOKASSA_RETURN_URL."
            ),
        )
    pack = manager.get_pack(sku)
    amount_value = yookassa_amount_for_pack(manager, pack)
    if amount_value is None:
        return CheckoutResult(
            ok=False,
            user_message=(
                "YooKassa pack amounts are not configured. Set "
                "BOTSPOT_SUBSCRIPTION_MANAGER_YOOKASSA_USD_RATE."
            ),
        )
    invoice = await manager._create_invoice(
        provider=PROVIDER_YOOKASSA,
        user_id=user_id,
        sku=pack.sku,
        title=pack.display_title,
        credits=pack.credits,
        amount_decimal=amount_value,
        currency="RUB",
        status=STATUS_PENDING,
        kind=KIND_PACK,
    )
    signature = sign_invoice_metadata(manager.settings, invoice.invoice_id, user_id)
    body = {
        "amount": {"value": amount_value, "currency": "RUB"},
        "capture": True,
        "confirmation": {"type": "redirect", "return_url": return_url},
        "description": f"{pack.display_title} ({pack.credits} credits)",
        "metadata": {
            "invoice_id": invoice.invoice_id,
            "telegram_user_id": str(user_id),
            "signature": signature,
        },
    }
    try:
        status, payload = await yookassa_request(
            manager, "POST", "/payments", json_body=body, idempotence_key=invoice.invoice_id
        )
    except SubscriptionPaymentError as e:
        await manager._fail_invoice(invoice.invoice_id, str(e))
        return CheckoutResult(
            ok=False,
            invoice=invoice,
            user_message="YooKassa is unavailable. Please try again later.",
        )
    if status >= 300:
        await manager._fail_invoice(invoice.invoice_id, json.dumps(payload))
        logger.warning(
            f"YooKassa payment failed for invoice {invoice.invoice_id}: {status} {payload}"
        )
        return CheckoutResult(
            ok=False,
            invoice=invoice,
            user_message="YooKassa payment failed. Please try again later.",
        )
    confirmation_url = (payload.get("confirmation") or {}).get("confirmation_url")
    if not confirmation_url:
        await manager._fail_invoice(invoice.invoice_id, json.dumps(payload))
        return CheckoutResult(
            ok=False, invoice=invoice, user_message="YooKassa did not return a confirmation URL."
        )
    await manager.invoices.update_one(
        {"_id": invoice.invoice_id},
        {
            "$set": {
                "status": STATUS_OPEN,
                "checkout_url": confirmation_url,
                "yookassa_payment_id": payload.get("id"),
                "provider_response": payload,
                "updated_at": manager._now(),
            }
        },
    )
    invoice.checkout_url = confirmation_url
    invoice.status = STATUS_OPEN
    return CheckoutResult(ok=True, invoice=invoice, checkout_url=confirmation_url)


async def handle_yookassa_event(manager: SubscriptionManager, event: dict[str, Any]) -> bool:
    if event.get("event") != "payment.succeeded":
        return False
    obj = event.get("object") or {}
    payment_id = str(obj.get("id") or "")
    if not payment_id:
        raise SubscriptionValidationError("YooKassa event is missing a payment id.")
    status, payment = await yookassa_request(manager, "GET", f"/payments/{payment_id}")
    if status >= 300:
        raise SubscriptionPaymentError(f"YooKassa reconcile failed for payment {payment_id}.")
    if payment.get("status") != "succeeded":
        return False
    metadata = payment.get("metadata") or {}
    invoice_id = str(metadata.get("invoice_id") or "")
    telegram_user_id = int(metadata.get("telegram_user_id") or 0)
    signature = str(metadata.get("signature") or "")
    if not invoice_id or not telegram_user_id:
        raise SubscriptionValidationError("YooKassa payment is missing invoice metadata.")
    if not verify_invoice_metadata(manager.settings, invoice_id, telegram_user_id, signature):
        raise SubscriptionValidationError("YooKassa invoice metadata signature is invalid.")
    invoice = await manager.invoices.find_one(
        {"_id": invoice_id, "telegram_user_id": telegram_user_id, "provider": PROVIDER_YOOKASSA}
    )
    if not invoice:
        raise SubscriptionValidationError(f"YooKassa invoice not found: {invoice_id}")
    credited = await manager._grant_invoice_credits(
        invoice=invoice,
        provider_event_id=f"yookassa:{payment_id}",
        metadata={"yookassa_payment": payment},
    )
    now = manager._now()
    await manager.invoices.update_one(
        {"_id": invoice_id},
        {
            "$set": {
                "status": "paid",
                "paid_at": now,
                "yookassa_payment_id": payment_id,
                "updated_at": now,
            }
        },
    )
    return credited
