"""
Subscription manager — tier-based feature gating for botspot bots.

Assign users to tiers (free, basic, pro, admin) and gate commands/features by tier.
Tiers are stored in MongoDB with admin commands to manage them.

Usage:
    # As a decorator on handlers:
    @require_tier("pro")
    async def pro_feature_handler(message: Message):
        ...

    # As a programmatic check:
    tier = await get_user_tier(user_id)
    if tier >= Tier.PRO:
        ...
"""

from enum import IntEnum
from typing import TYPE_CHECKING, List, Optional

from aiogram.filters import Command
from aiogram.types import Message
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from botspot.components.middlewares.i18n import t
from botspot.utils.internal import get_logger

if TYPE_CHECKING:
    from pymongo.asynchronous.collection import AsyncCollection  # noqa: F401

logger = get_logger()


class Tier(IntEnum):
    """User subscription tiers, ordered by access level."""

    FREE = 0
    BASIC = 10
    PRO = 20
    ADMIN = 100


# String-to-tier mapping for CLI/command parsing
TIER_NAMES = {tier.name.lower(): tier for tier in Tier}


class SubscriptionManagerSettings(BaseSettings):
    enabled: bool = False
    mongo_collection: str = "subscription_manager"
    default_tier: str = "free"
    commands_visible: bool = False

    class Config:
        env_prefix = "BOTSPOT_SUBSCRIPTION_MANAGER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class UserSubscription(BaseModel):
    user_id: int
    tier: str = "free"
    granted_by: Optional[int] = None  # admin who set the tier


class SubscriptionManager:
    def __init__(
        self,
        settings: SubscriptionManagerSettings,
        collection: Optional["AsyncCollection"] = None,
    ):
        self.settings = settings
        if collection is None:
            from botspot.utils.deps_getters import get_database

            db = get_database()
            collection = db.get_collection(settings.mongo_collection)
        self.collection = collection
        self._default_tier = _parse_tier(settings.default_tier)

    async def get_user_tier(self, user_id: int) -> Tier:
        """Get a user's current tier. Returns default_tier if not set."""
        # Admins always get ADMIN tier
        from botspot.utils.user_ops import is_admin

        if is_admin(user_id):
            return Tier.ADMIN

        record = await self.collection.find_one({"user_id": user_id})
        if record is None:
            return self._default_tier
        return _parse_tier(record.get("tier", self.settings.default_tier))

    async def set_user_tier(
        self, user_id: int, tier: Tier, granted_by: Optional[int] = None
    ) -> UserSubscription:
        """Set a user's tier. Creates or updates the record."""
        sub = UserSubscription(user_id=user_id, tier=tier.name.lower(), granted_by=granted_by)
        await self.collection.update_one(
            {"user_id": user_id},
            {"$set": sub.model_dump()},
            upsert=True,
        )
        logger.info(f"Set tier for user {user_id} to {tier.name}")
        return sub

    async def remove_user_tier(self, user_id: int) -> bool:
        """Remove a user's tier record (revert to default)."""
        result = await self.collection.delete_one({"user_id": user_id})
        return result.deleted_count > 0

    async def list_subscribers(self, tier: Optional[Tier] = None) -> List[UserSubscription]:
        """List all users with explicit tier records, optionally filtered by tier."""
        query = {}
        if tier is not None:
            query["tier"] = tier.name.lower()
        records = await self.collection.find(query).to_list(length=1000)
        return [UserSubscription(**r) for r in records]


def _parse_tier(value: str) -> Tier:
    """Parse a tier string to Tier enum, defaulting to FREE."""
    return TIER_NAMES.get(value.lower(), Tier.FREE)


# --- Getter ---


def get_subscription_manager() -> SubscriptionManager:
    """Get the SubscriptionManager instance from dependency manager."""
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    return deps.subscription_manager


# --- Wrapper functions ---


async def get_user_tier(user_id: int) -> Tier:
    """Get a user's current tier."""
    sm = get_subscription_manager()
    return await sm.get_user_tier(user_id)


async def set_user_tier(
    user_id: int, tier: Tier, granted_by: Optional[int] = None
) -> UserSubscription:
    """Set a user's tier."""
    sm = get_subscription_manager()
    return await sm.set_user_tier(user_id, tier, granted_by)


async def check_tier(user_id: int, required: Tier) -> bool:
    """Check if a user meets the required tier."""
    user_tier = await get_user_tier(user_id)
    return user_tier >= required


# --- Decorator ---


def require_tier(tier_name: str):
    """Decorator to gate a handler behind a minimum tier.

    Usage:
        @require_tier("pro")
        @router.message(Command("pro_feature"))
        async def pro_feature_handler(message: Message):
            ...
    """
    from functools import wraps

    required = _parse_tier(tier_name)

    def decorator(func):
        @wraps(func)
        async def wrapper(message: Message, *args, **kwargs):
            if message.from_user is None:
                return
            user_tier = await get_user_tier(message.from_user.id)
            if user_tier < required:
                await message.reply(
                    t(
                        "subscription.tier_required",
                        required=required.name.lower(),
                        current=user_tier.name.lower(),
                    )
                )
                return
            return await func(message, *args, **kwargs)

        return wrapper

    return decorator


# --- Command handlers ---


async def _set_tier_handler(message: Message):
    """Admin command: /set_tier <user_id_or_username> <tier_name>"""

    assert message.from_user is not None
    if message.text is None:
        return

    parts = message.text.split()
    # /set_tier <target> <tier>
    if len(parts) < 3:
        await message.reply(t("subscription.set_tier_usage"))
        return

    target_str = parts[1]
    tier_str = parts[2].lower()

    if tier_str not in TIER_NAMES:
        await message.reply(
            t("subscription.invalid_tier", tier=tier_str, valid=", ".join(TIER_NAMES.keys()))
        )
        return

    # Resolve target to user_id
    target_id = int(target_str) if target_str.isdigit() else None
    if target_id is None:
        # Try to resolve username via user_data if available
        try:
            from botspot.components.data.user_data import get_user_manager

            um = get_user_manager()
            user = await um.get_user_by_username(target_str.lstrip("@"))
            if user:
                target_id = user.user_id
        except Exception:
            pass

    if target_id is None:
        await message.reply(t("subscription.user_not_found", target=target_str))
        return

    tier = TIER_NAMES[tier_str]
    await set_user_tier(target_id, tier, granted_by=message.from_user.id)
    await message.reply(t("subscription.tier_set", target=target_str, tier=tier.name.lower()))


async def _my_tier_handler(message: Message):
    """Show the current user's tier."""
    assert message.from_user is not None
    tier = await get_user_tier(message.from_user.id)
    await message.reply(t("subscription.my_tier", tier=tier.name.lower()))


async def _list_subscribers_handler(message: Message):
    """Admin command: list all users with explicit tier records."""
    sm = get_subscription_manager()
    subs = await sm.list_subscribers()
    if not subs:
        await message.reply(t("subscription.list_empty"))
        return

    lines = [f"• {s.user_id}: {s.tier}" for s in subs]
    await message.reply(t("subscription.list_header", entries="\n".join(lines)))


# --- Component lifecycle ---


def setup_dispatcher(dp):
    """Register subscription manager handlers."""
    dp.message.register(_set_tier_handler, Command("set_tier"))
    dp.message.register(_my_tier_handler, Command("my_tier"))
    dp.message.register(_list_subscribers_handler, Command("list_subscribers"))
    return dp


def initialize(settings: SubscriptionManagerSettings) -> SubscriptionManager:
    """Initialize the subscription_manager component."""
    from botspot.core.dependency_manager import get_dependency_manager
    from botspot.core.errors import ConfigurationError

    deps = get_dependency_manager()
    if not deps.botspot_settings.mongo_database.enabled:
        raise ConfigurationError(
            "MongoDB is required for subscription_manager. Set BOTSPOT_MONGO_DATABASE_ENABLED=true"
        )

    from botspot.components.qol.bot_commands_menu import Visibility, add_command

    visibility = Visibility.PUBLIC if settings.commands_visible else Visibility.HIDDEN
    admin_vis = Visibility.ADMIN_ONLY if settings.commands_visible else Visibility.HIDDEN

    add_command("my_tier", "Show your subscription tier", visibility=visibility)(_my_tier_handler)
    add_command("set_tier", "Set a user's tier (admin)", visibility=admin_vis)(_set_tier_handler)
    add_command("list_subscribers", "List all subscribers (admin)", visibility=admin_vis)(
        _list_subscribers_handler
    )

    return SubscriptionManager(settings)
