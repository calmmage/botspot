"""Settings for the subscription_manager component."""

from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings

TELEGRAM_STARS_PERIOD_SECONDS = 2592000
TELEGRAM_STARS_MAX_AMOUNT = 10000
STRIPE_API_VERSION = "2026-08-26.dahlia"
STRIPE_CHECKOUT_SESSIONS_URL = "https://api.stripe.com/v1/checkout/sessions"
STRIPE_CUSTOMERS_URL = "https://api.stripe.com/v1/customers"
STRIPE_BILLING_PORTAL_SESSIONS_URL = "https://api.stripe.com/v1/billing_portal/sessions"
STRIPE_WEBHOOK_PATH = "/api/billing/stripe/webhook"
YOOKASSA_WEBHOOK_PATH = "/api/billing/yookassa/webhook"
YOOKASSA_API_BASE = "https://api.yookassa.ru/v3"

PROVIDER_STRIPE = "stripe"
PROVIDER_STARS = "telegram_stars"
PROVIDER_TON_MANUAL = "ton_manual"
PROVIDER_YOOKASSA = "yookassa"
PROVIDER_MANUAL = "manual"

STATUS_PENDING = "pending"
STATUS_OPEN = "open"
STATUS_PROOF_SUBMITTED = "proof_submitted"
STATUS_PAID = "paid"
STATUS_FAILED = "failed"

SUB_ACTIVE = "active"
SUB_CANCELLED = "cancelled"
SUB_PAST_DUE = "past_due"
SUB_EXPIRED = "expired"

SOURCE_ADMIN = "admin"
SOURCE_FRIEND = "friend"
SOURCE_SUBSCRIPTION = "subscription"
SOURCE_CREDITS = "credits"
SOURCE_TRIAL = "trial"
SOURCE_MANUAL = "manual"
SOURCE_NONE = "none"

PAID_SOURCES = frozenset(
    {SOURCE_ADMIN, SOURCE_FRIEND, SOURCE_SUBSCRIPTION, SOURCE_CREDITS, SOURCE_MANUAL}
)

KIND_PACK = "pack"
KIND_SUBSCRIPTION = "subscription"

PAYLOAD_PREFIX = "b"
PAYLOAD_SIGNATURE_BYTES = 18
PAYLOAD_PROVIDER_CODES = {
    PROVIDER_STRIPE: "sp",
    PROVIDER_STARS: "ts",
    PROVIDER_TON_MANUAL: "tm",
    PROVIDER_YOOKASSA: "yk",
    PROVIDER_MANUAL: "mn",
}
PAYLOAD_CODE_PROVIDERS = {code: provider for provider, code in PAYLOAD_PROVIDER_CODES.items()}

STRIPE_FULFILL_EVENT_TYPES = frozenset(
    {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
    }
)
STRIPE_FAIL_EVENT_TYPES = frozenset(
    {"checkout.session.async_payment_failed", "invoice.payment_failed"}
)
STRIPE_PAID_STATUSES = frozenset({"paid", "no_payment_required"})
STRIPE_RENEW_EVENT_TYPES = frozenset({"invoice.paid"})
STRIPE_CANCEL_EVENT_TYPES = frozenset({"customer.subscription.deleted"})


class SubscriptionManagerSettings(BaseSettings):
    """Env prefix ``BOTSPOT_SUBSCRIPTION_MANAGER_``."""

    enabled: bool = False
    register_commands: bool = True
    collection_prefix: str = "billing_"
    credits_per_usd: int = 100
    stars_per_usd: int = 100
    media_cost_multiplier: float = 1.6
    chat_cost_multiplier: float = 1.2
    grace_days: int = 2
    reconcile_interval_hours: int = 6
    signature_secret: SecretStr | None = None
    plans_json: str = ""
    packs_json: str = ""
    trial_enabled: bool = True
    trial_duration_days: int = 7
    trial_user_audio_requests_total: int = 20
    trial_user_audio_minutes_total: float = 90.0
    trial_user_chat_requests_total: int = 200
    trial_user_chat_tokens_total: int = 60000
    trial_global_audio_requests_per_day: int = 100
    trial_global_audio_minutes_per_day: float = 480.0
    trial_global_chat_requests_per_day: int = 1000
    trial_global_chat_tokens_per_day: int = 400000
    trial_global_cost_usd_per_day: float = 2.0
    trial_daily_cost_alert_thresholds: str = "0.5,1.0,1.5,2.0"
    trial_unknown_media_minutes_default: float = 10.0
    trial_media_cost_per_minute_usd: float = 0.006
    stripe_secret_key: SecretStr | None = None
    stripe_webhook_secret: SecretStr | None = None
    stripe_allow_live: bool = False
    stripe_price_ids_json: str = ""
    stripe_integration_identifier_prefix: str = "botspot"
    public_base_url: str = ""
    yookassa_shop_id: str = ""
    yookassa_secret_key: SecretStr | None = None
    yookassa_return_url: str = ""
    yookassa_usd_rate: float = 0.0
    ton_wallet_address: str = ""
    ton_usd_rate: float = 0.0

    class Config:
        env_prefix = "BOTSPOT_SUBSCRIPTION_MANAGER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
