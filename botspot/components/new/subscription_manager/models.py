"""Pydantic models for subscription_manager."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

ProviderName = Literal["telegram_stars", "stripe", "manual"]
SubscriptionStatus = Literal["active", "cancelled", "past_due", "expired"]
EntitlementSource = Literal["admin", "friend", "subscription", "credits", "trial", "manual", "none"]


class Plan(BaseModel):
    """A recurring entitlement plan (Stars native subscription or Stripe)."""

    plan_id: str
    title: str
    period_days: int = 30
    stars: int
    usd_cents: int
    minutes_per_period: float | None = None
    credits_per_period: int | None = None
    features: list[str] = Field(default_factory=list)
    seats: int = 1
    stripe_price_id: str = ""


class CreditPack(BaseModel):
    """One-off credit pack. Whisper-compatible plus Stars/Stripe ids."""

    model_config = ConfigDict(frozen=True)

    sku: str
    credits: int
    usd_cents: int
    stars: int
    stripe_price_id: str = ""
    title: str = ""

    @property
    def usd_amount(self) -> float:
        return self.usd_cents / 100

    @property
    def display_title(self) -> str:
        return self.title or f"${self.usd_amount:.0f} credit pack"


class Subscription(BaseModel):
    """A user's recurring plan row."""

    user_id: int
    plan_id: str
    provider: ProviderName
    provider_sub_id: str = ""
    provider_charge_id: str = ""
    status: SubscriptionStatus = "active"
    started_at: datetime
    current_period_end: datetime
    cancel_at_period_end: bool = False
    granted_by: int | None = None


class Entitlement(BaseModel):
    """Denormalised access snapshot for the hot path."""

    user_id: int
    plan_id: str | None = None
    source: EntitlementSource = "none"
    until: datetime | None = None
    minutes_left: float | None = None
    credits: int = 0


class Decision(BaseModel):
    """Result of ``authorize`` (whisper BillingDecision + trial merged)."""

    allowed: bool
    source: str
    hold_id: str | None = None
    reason: str = ""
    message_key: str = ""


class Balance(BaseModel):
    """Credit wallet snapshot (whisper BillingBalance)."""

    telegram_user_id: int
    balance_credits: int
    retail_usd: float
    audio_minutes: float


class Invoice(BaseModel):
    """Provider invoice (whisper BillingInvoice)."""

    invoice_id: str
    provider: str
    sku: str
    title: str
    telegram_user_id: int
    username: Optional[str] = None
    credits: int = 0
    amount_minor: Optional[int] = None
    amount_decimal: Optional[str] = None
    currency: str
    status: str
    payment_payload: Optional[str] = None
    checkout_url: Optional[str] = None
    ton_wallet_address: Optional[str] = None
    ton_memo: Optional[str] = None
    user_message: Optional[str] = None
    plan_id: Optional[str] = None
    kind: str = "pack"


class CheckoutResult(BaseModel):
    """Adapter result for YooKassa/TON (whisper BillingProviderResult)."""

    ok: bool
    invoice: Optional[Invoice] = None
    checkout_url: Optional[str] = None
    user_message: Optional[str] = None
