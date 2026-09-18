"""TON manual invoice + proof-submitted flow (whisper port)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from botspot.components.new.subscription_manager.models import CheckoutResult
from botspot.components.new.subscription_manager.settings import (
    KIND_PACK,
    PROVIDER_TON_MANUAL,
    STATUS_PENDING,
    STATUS_PROOF_SUBMITTED,
)
from botspot.core.errors import SubscriptionValidationError

if TYPE_CHECKING:
    from botspot.components.new.subscription_manager.manager import SubscriptionManager
    from botspot.components.new.subscription_manager.models import CreditPack


def ton_amount_for_pack(manager: SubscriptionManager, pack: CreditPack) -> Optional[str]:
    usd_rate = float(manager.settings.ton_usd_rate or 0.0)
    if usd_rate <= 0:
        return None
    return f"{pack.usd_amount / usd_rate:.4f}".rstrip("0").rstrip(".")


async def create_ton_manual_invoice(
    manager: SubscriptionManager, user_id: int, sku: str
) -> CheckoutResult:
    wallet = manager.settings.ton_wallet_address
    if not wallet:
        return CheckoutResult(
            ok=False,
            user_message=(
                "TON payments are not configured. Set "
                "BOTSPOT_SUBSCRIPTION_MANAGER_TON_WALLET_ADDRESS."
            ),
        )
    pack = manager.get_pack(sku)
    amount = ton_amount_for_pack(manager, pack)
    if amount is None:
        return CheckoutResult(
            ok=False,
            user_message=(
                "TON pack amounts are not configured. Set "
                "BOTSPOT_SUBSCRIPTION_MANAGER_TON_USD_RATE."
            ),
        )
    invoice = await manager._create_invoice(
        provider=PROVIDER_TON_MANUAL,
        user_id=user_id,
        sku=pack.sku,
        title=pack.display_title,
        credits=pack.credits,
        amount_decimal=amount,
        currency="TON",
        status=STATUS_PENDING,
        kind=KIND_PACK,
        ton_wallet_address=wallet,
    )
    memo = f"botspot-{invoice.invoice_id}"
    await manager.invoices.update_one(
        {"_id": invoice.invoice_id},
        {"$set": {"ton_memo": memo, "updated_at": manager._now()}},
    )
    invoice.ton_memo = memo
    invoice.ton_wallet_address = wallet
    return CheckoutResult(ok=True, invoice=invoice)


async def record_ton_proof(
    manager: SubscriptionManager, telegram_user_id: int, invoice_id: str, proof_text: str
) -> bool:
    now = manager._now()
    result = await manager.invoices.update_one(
        {
            "_id": invoice_id,
            "telegram_user_id": int(telegram_user_id),
            "provider": PROVIDER_TON_MANUAL,
            "status": {"$in": [STATUS_PENDING, STATUS_PROOF_SUBMITTED]},
        },
        {
            "$set": {
                "status": STATUS_PROOF_SUBMITTED,
                "proof_text": proof_text,
                "proof_submitted_at": now,
                "updated_at": now,
            }
        },
    )
    return int(getattr(result, "modified_count", 0)) > 0


async def confirm_manual_invoice(
    manager: SubscriptionManager, invoice_id: str, admin_user_id: int
) -> bool:
    invoice = await manager.invoices.find_one({"_id": invoice_id, "provider": PROVIDER_TON_MANUAL})
    if not invoice:
        raise SubscriptionValidationError(f"TON invoice not found: {invoice_id}")
    credited = await manager._grant_invoice_credits(
        invoice=invoice,
        provider_event_id=f"ton_manual:{invoice_id}",
        metadata={"confirmed_by": int(admin_user_id)},
    )
    now = manager._now()
    await manager.invoices.update_one(
        {"_id": invoice_id},
        {
            "$set": {
                "status": "paid",
                "paid_at": now,
                "confirmed_by": int(admin_user_id),
                "updated_at": now,
            }
        },
    )
    return credited
