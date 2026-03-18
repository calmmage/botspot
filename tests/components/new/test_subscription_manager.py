"""Tests for the subscription_manager component."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from botspot.components.new.subscription_manager import (
    SubscriptionManager,
    SubscriptionManagerSettings,
    Tier,
    UserSubscription,
    _parse_tier,
    require_tier,
)


class TestTier:
    def test_tier_ordering(self):
        """Tiers are ordered: FREE < BASIC < PRO < ADMIN."""
        assert Tier.FREE < Tier.BASIC < Tier.PRO < Tier.ADMIN

    def test_tier_comparison(self):
        """Tier comparison works for gating checks."""
        assert Tier.PRO >= Tier.BASIC
        assert Tier.FREE < Tier.PRO
        assert Tier.ADMIN >= Tier.PRO


class TestParseTier:
    def test_valid_tiers(self):
        assert _parse_tier("free") == Tier.FREE
        assert _parse_tier("basic") == Tier.BASIC
        assert _parse_tier("pro") == Tier.PRO
        assert _parse_tier("admin") == Tier.ADMIN

    def test_case_insensitive(self):
        assert _parse_tier("PRO") == Tier.PRO
        assert _parse_tier("Basic") == Tier.BASIC

    def test_unknown_defaults_to_free(self):
        assert _parse_tier("unknown") == Tier.FREE
        assert _parse_tier("") == Tier.FREE


class TestSubscriptionManagerSettings:
    def test_default_settings(self):
        with pytest.MonkeyPatch.context() as mp:
            mp.delenv("BOTSPOT_SUBSCRIPTION_MANAGER_ENABLED", raising=False)
            mp.delenv("BOTSPOT_SUBSCRIPTION_MANAGER_MONGO_COLLECTION", raising=False)
            mp.delenv("BOTSPOT_SUBSCRIPTION_MANAGER_DEFAULT_TIER", raising=False)

            settings = SubscriptionManagerSettings()

            assert settings.enabled is False
            assert settings.mongo_collection == "subscription_manager"
            assert settings.default_tier == "free"

    def test_settings_from_env(self):
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("BOTSPOT_SUBSCRIPTION_MANAGER_ENABLED", "True")
            mp.setenv("BOTSPOT_SUBSCRIPTION_MANAGER_MONGO_COLLECTION", "subs")
            mp.setenv("BOTSPOT_SUBSCRIPTION_MANAGER_DEFAULT_TIER", "basic")

            settings = SubscriptionManagerSettings()

            assert settings.enabled is True
            assert settings.mongo_collection == "subs"
            assert settings.default_tier == "basic"


class TestUserSubscription:
    def test_default_values(self):
        sub = UserSubscription(user_id=123)
        assert sub.user_id == 123
        assert sub.tier == "free"
        assert sub.granted_by is None

    def test_custom_values(self):
        sub = UserSubscription(user_id=123, tier="pro", granted_by=456)
        assert sub.tier == "pro"
        assert sub.granted_by == 456


class TestSubscriptionManager:
    @pytest.fixture
    def mock_collection(self):
        collection = AsyncMock()
        return collection

    @pytest.fixture
    def manager(self, mock_collection):
        settings = SubscriptionManagerSettings()
        return SubscriptionManager(settings, collection=mock_collection)

    @pytest.mark.asyncio
    async def test_get_user_tier_default(self, manager, mock_collection):
        """Returns default tier when no record exists."""
        mock_collection.find_one = AsyncMock(return_value=None)
        with patch("botspot.utils.user_ops.is_admin", return_value=False):
            tier = await manager.get_user_tier(123)
        assert tier == Tier.FREE

    @pytest.mark.asyncio
    async def test_get_user_tier_from_db(self, manager, mock_collection):
        """Returns tier from database record."""
        mock_collection.find_one = AsyncMock(return_value={"user_id": 123, "tier": "pro"})
        with patch("botspot.utils.user_ops.is_admin", return_value=False):
            tier = await manager.get_user_tier(123)
        assert tier == Tier.PRO

    @pytest.mark.asyncio
    async def test_get_user_tier_admin_override(self, manager, mock_collection):
        """Admins always get ADMIN tier regardless of DB."""
        mock_collection.find_one = AsyncMock(return_value={"user_id": 123, "tier": "free"})
        with patch("botspot.utils.user_ops.is_admin", return_value=True):
            tier = await manager.get_user_tier(123)
        assert tier == Tier.ADMIN

    @pytest.mark.asyncio
    async def test_set_user_tier(self, manager, mock_collection):
        """Sets tier and upserts to DB."""
        mock_collection.update_one = AsyncMock()
        sub = await manager.set_user_tier(123, Tier.PRO, granted_by=456)

        assert sub.user_id == 123
        assert sub.tier == "pro"
        assert sub.granted_by == 456
        mock_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_user_tier(self, manager, mock_collection):
        """Removes tier record from DB."""
        mock_collection.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
        result = await manager.remove_user_tier(123)
        assert result is True

    @pytest.mark.asyncio
    async def test_remove_user_tier_not_found(self, manager, mock_collection):
        """Returns False when no record to remove."""
        mock_collection.delete_one = AsyncMock(return_value=MagicMock(deleted_count=0))
        result = await manager.remove_user_tier(999)
        assert result is False

    @pytest.mark.asyncio
    async def test_list_subscribers(self, manager, mock_collection):
        """Lists all subscribers."""
        mock_cursor = AsyncMock()
        mock_cursor.to_list = AsyncMock(
            return_value=[
                {"user_id": 1, "tier": "basic"},
                {"user_id": 2, "tier": "pro"},
            ]
        )
        mock_collection.find = MagicMock(return_value=mock_cursor)

        subs = await manager.list_subscribers()
        assert len(subs) == 2
        assert subs[0].tier == "basic"
        assert subs[1].tier == "pro"

    @pytest.mark.asyncio
    async def test_list_subscribers_filtered(self, manager, mock_collection):
        """Lists subscribers filtered by tier."""
        mock_cursor = AsyncMock()
        mock_cursor.to_list = AsyncMock(return_value=[{"user_id": 2, "tier": "pro"}])
        mock_collection.find = MagicMock(return_value=mock_cursor)

        subs = await manager.list_subscribers(tier=Tier.PRO)
        mock_collection.find.assert_called_with({"tier": "pro"})
        assert len(subs) == 1


class TestRequireTierDecorator:
    @pytest.mark.asyncio
    async def test_blocks_insufficient_tier(self):
        """Decorator blocks users below required tier."""
        inner = AsyncMock()
        decorated = require_tier("pro")(inner)

        message = AsyncMock()
        message.from_user = MagicMock()
        message.from_user.id = 123
        message.reply = AsyncMock()

        with patch(
            "botspot.components.new.subscription_manager.get_user_tier",
            new_callable=AsyncMock,
            return_value=Tier.FREE,
        ):
            await decorated(message)

        inner.assert_not_called()
        message.reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_allows_sufficient_tier(self):
        """Decorator allows users at or above required tier."""
        inner = AsyncMock()
        decorated = require_tier("basic")(inner)

        message = AsyncMock()
        message.from_user = MagicMock()
        message.from_user.id = 123

        with patch(
            "botspot.components.new.subscription_manager.get_user_tier",
            new_callable=AsyncMock,
            return_value=Tier.PRO,
        ):
            await decorated(message)

        inner.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_no_user(self):
        """Decorator skips messages with no from_user."""
        inner = AsyncMock()
        decorated = require_tier("basic")(inner)

        message = AsyncMock()
        message.from_user = None

        await decorated(message)
        inner.assert_not_called()
