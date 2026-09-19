"""botspot subscription_manager component.

Credits ledger, Telegram Stars one-off invoices and native subscriptions,
Stripe/YooKassa/TON adapters, trial caps, and friend/admin bypass.

Per-user daily trial caps (env prefix ``BOTSPOT_SUBSCRIPTION_MANAGER_``, 0 = off):
``TRIAL_USER_AUDIO_MINUTES_PER_DAY``, ``TRIAL_USER_AUDIO_REQUESTS_PER_DAY``,
``TRIAL_USER_CHAT_REQUESTS_PER_DAY``. ``TRIAL_DURATION_DAYS=0`` means no expiry
(public free tier). Hitting a per-user daily cap sets ``Decision.reason`` to
``trial_daily_cap``.
"""

from __future__ import annotations

from botspot.components.new.subscription_manager.handlers import (
    register_command_handlers,
    register_payment_handlers,
    require_plan,
    setup_dispatcher,
)
from botspot.components.new.subscription_manager.manager import SubscriptionManager
from botspot.components.new.subscription_manager.models import (
    Balance,
    CheckoutResult,
    CreditPack,
    Decision,
    Entitlement,
    Invoice,
    Plan,
    Subscription,
)
from botspot.components.new.subscription_manager.settings import (
    STRIPE_WEBHOOK_PATH,
    YOOKASSA_WEBHOOK_PATH,
    SubscriptionManagerSettings,
)
from botspot.components.new.subscription_manager.web import aiohttp_routes
from botspot.utils.internal import get_logger

logger = get_logger()


def initialize(
    settings: SubscriptionManagerSettings,
    *,
    plans: list[Plan] | None = None,
    packs: list[CreditPack] | None = None,
) -> SubscriptionManager:
    """Initialize the component. Requires mongo_database enabled."""
    from botspot.core.dependency_manager import get_dependency_manager
    from botspot.core.errors import ConfigurationError

    deps = get_dependency_manager()
    if not deps.botspot_settings.mongo_database.enabled:
        raise ConfigurationError(
            "MongoDB is required for subscription_manager. Set BOTSPOT_MONGO_DATABASE_ENABLED=true."
        )
    from botspot.components.data.mongo_database import get_database

    db = get_database()
    bot = None
    try:
        bot = deps.bot
    except Exception:
        bot = None
    manager = SubscriptionManager(settings, db=db, plans=plans, packs=packs, bot=bot)
    logger.info("subscription_manager initialized")
    return manager


def get_subscription_manager() -> SubscriptionManager:
    from botspot.core.dependency_manager import get_dependency_manager

    return get_dependency_manager().subscription_manager


__all__ = [
    "SubscriptionManagerSettings",
    "SubscriptionManager",
    "Plan",
    "CreditPack",
    "Subscription",
    "Entitlement",
    "Decision",
    "Balance",
    "Invoice",
    "CheckoutResult",
    "initialize",
    "setup_dispatcher",
    "register_command_handlers",
    "register_payment_handlers",
    "get_subscription_manager",
    "require_plan",
    "STRIPE_WEBHOOK_PATH",
    "YOOKASSA_WEBHOOK_PATH",
    "aiohttp_routes",
]
