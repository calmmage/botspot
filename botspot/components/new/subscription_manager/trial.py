"""Trial caps (whisper trial_limits.py), friends/admins bypass via user_ops."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any, Optional

from botspot.components.new.subscription_manager.settings import SubscriptionManagerSettings
from botspot.utils.internal import get_logger

logger = get_logger()


@dataclass
class TrialDecision:
    allowed: bool
    message_key: str = ""
    alert_message: Optional[str] = None
    bypassed: bool = False


class TrialLimiter:
    """Per-user + global $2/day caps. Admins/friends bypass."""

    TRIAL_USERS_COLLECTION = "trial_users"
    TRIAL_DAILY_COLLECTION = "trial_daily_usage"

    def __init__(self, db: Any, settings: SubscriptionManagerSettings):
        self.db = db
        self.settings = settings
        self._alert_thresholds = self._parse_alert_thresholds(
            settings.trial_daily_cost_alert_thresholds
        )

    @property
    def trial_users(self):
        return self.db.get_collection(self.TRIAL_USERS_COLLECTION)

    @property
    def trial_daily_usage(self):
        return self.db.get_collection(self.TRIAL_DAILY_COLLECTION)

    @staticmethod
    def _parse_alert_thresholds(raw_thresholds: str) -> list[float]:
        values = []
        for item in raw_thresholds.split(","):
            item = item.strip()
            if not item:
                continue
            try:
                value = float(item)
            except ValueError:
                continue
            if value > 0:
                values.append(value)
        if not values:
            values = [0.5, 1.0, 1.5, 2.0]
        return sorted(set(values))

    @staticmethod
    def _utc_day_key(now: datetime.datetime) -> str:
        return now.strftime("%Y-%m-%d")

    @staticmethod
    def _limit_exceeded(current: float, increment: float, limit: float) -> bool:
        if limit <= 0:
            return False
        return (current + increment) > limit

    def is_bypass_user(self, user_id: int) -> bool:
        try:
            from botspot.utils.user_ops import is_admin, is_friend

            if is_admin(user_id) or is_friend(user_id):
                return True
        except Exception as e:
            logger.warning(f"Failed to check bypass role for user {user_id}: {e}")
        return False

    async def reserve(
        self,
        user_id: int,
        *,
        kind: str,
        estimated_minutes: float = 0,
        estimated_tokens: int = 0,
        estimated_cost_usd: float = 0,
        username: Optional[str] = None,
    ) -> TrialDecision:
        if not self.settings.trial_enabled:
            return TrialDecision(allowed=True, bypassed=True)

        if self.is_bypass_user(user_id):
            return TrialDecision(allowed=True, bypassed=True)

        audio_requests = 1 if kind == "audio" else 0
        audio_minutes = max(1.0, float(estimated_minutes)) if kind == "audio" else 0.0
        chat_requests = 1 if kind == "chat" else 0
        chat_tokens = max(1, int(estimated_tokens)) if kind == "chat" else 0
        estimated_cost_usd = max(0.0, float(estimated_cost_usd))

        now_utc = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        day_key = self._utc_day_key(now_utc)
        await self._upsert_trial_user_identity(user_id, username, now_utc)
        trial_user = await self.trial_users.find_one({"_id": user_id})
        assert trial_user is not None

        expires_at = trial_user.get("expires_at")
        if isinstance(expires_at, datetime.datetime) and now_utc > expires_at:
            return TrialDecision(allowed=False, message_key="trial_expired")

        if self._limit_exceeded(
            int(trial_user.get("audio_requests_used_total", 0)),
            audio_requests,
            float(self.settings.trial_user_audio_requests_total),
        ):
            return TrialDecision(allowed=False, message_key="trial_audio_requests_cap")
        if self._limit_exceeded(
            float(trial_user.get("audio_minutes_used_total", 0.0)),
            audio_minutes,
            float(self.settings.trial_user_audio_minutes_total),
        ):
            return TrialDecision(allowed=False, message_key="trial_audio_minutes_cap")
        if self._limit_exceeded(
            int(trial_user.get("chat_requests_used_total", 0)),
            chat_requests,
            float(self.settings.trial_user_chat_requests_total),
        ):
            return TrialDecision(allowed=False, message_key="trial_chat_requests_cap")
        if self._limit_exceeded(
            int(trial_user.get("chat_tokens_used_total", 0)),
            float(chat_tokens),
            float(self.settings.trial_user_chat_tokens_total),
        ):
            return TrialDecision(allowed=False, message_key="trial_chat_tokens_cap")

        daily = await self.trial_daily_usage.find_one({"_id": day_key})
        if daily is None:
            daily = {
                "_id": day_key,
                "audio_requests_reserved": 0,
                "audio_minutes_reserved": 0.0,
                "chat_requests_reserved": 0,
                "chat_tokens_reserved": 0,
                "cost_reserved_usd": 0.0,
                "alert_level": 0,
            }

        if self._limit_exceeded(
            int(daily.get("audio_requests_reserved", 0)),
            audio_requests,
            float(self.settings.trial_global_audio_requests_per_day),
        ):
            return TrialDecision(allowed=False, message_key="trial_global_audio_requests_day")
        if self._limit_exceeded(
            float(daily.get("audio_minutes_reserved", 0.0)),
            audio_minutes,
            float(self.settings.trial_global_audio_minutes_per_day),
        ):
            return TrialDecision(allowed=False, message_key="trial_global_audio_minutes_day")
        if self._limit_exceeded(
            int(daily.get("chat_requests_reserved", 0)),
            chat_requests,
            float(self.settings.trial_global_chat_requests_per_day),
        ):
            return TrialDecision(allowed=False, message_key="trial_global_chat_requests_day")
        if self._limit_exceeded(
            int(daily.get("chat_tokens_reserved", 0)),
            float(chat_tokens),
            float(self.settings.trial_global_chat_tokens_per_day),
        ):
            return TrialDecision(allowed=False, message_key="trial_global_chat_tokens_day")
        if self._limit_exceeded(
            float(daily.get("cost_reserved_usd", 0.0)),
            estimated_cost_usd,
            float(self.settings.trial_global_cost_usd_per_day),
        ):
            return TrialDecision(allowed=False, message_key="trial_global_cost_day")

        await self.trial_users.update_one(
            {"_id": user_id},
            {
                "$inc": {
                    "audio_requests_used_total": audio_requests,
                    "audio_minutes_used_total": audio_minutes,
                    "chat_requests_used_total": chat_requests,
                    "chat_tokens_used_total": chat_tokens,
                },
                "$set": {"username": username, "updated_at": now_utc},
            },
            upsert=True,
        )
        await self.trial_daily_usage.update_one(
            {"_id": day_key},
            {
                "$setOnInsert": {
                    "created_at": now_utc,
                    "alert_level": int(daily.get("alert_level", 0)),
                },
                "$inc": {
                    "audio_requests_reserved": audio_requests,
                    "audio_minutes_reserved": audio_minutes,
                    "chat_requests_reserved": chat_requests,
                    "chat_tokens_reserved": chat_tokens,
                    "cost_reserved_usd": estimated_cost_usd,
                },
                "$set": {"updated_at": now_utc},
            },
            upsert=True,
        )
        updated_daily = await self.trial_daily_usage.find_one({"_id": day_key})
        alert_message = await self._maybe_build_alert_message(updated_daily, now_utc)
        return TrialDecision(allowed=True, alert_message=alert_message, bypassed=False)

    async def is_trial_active(self, user_id: int) -> bool:
        if not self.settings.trial_enabled:
            return False
        now_utc = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        trial_user = await self.trial_users.find_one({"_id": int(user_id)})
        if trial_user is None:
            return True
        expires_at = trial_user.get("expires_at")
        if isinstance(expires_at, datetime.datetime) and now_utc > expires_at:
            return False
        return True

    async def _upsert_trial_user_identity(
        self, user_id: int, username: Optional[str], now_utc: datetime.datetime
    ) -> None:
        trial_days = int(self.settings.trial_duration_days)
        expires_at = now_utc + datetime.timedelta(days=trial_days)
        await self.trial_users.update_one(
            {"_id": user_id},
            {
                "$setOnInsert": {
                    "started_at": now_utc,
                    "expires_at": expires_at,
                    "audio_requests_used_total": 0,
                    "audio_minutes_used_total": 0.0,
                    "chat_requests_used_total": 0,
                    "chat_tokens_used_total": 0,
                    "created_at": now_utc,
                },
                "$set": {"username": username, "updated_at": now_utc},
            },
            upsert=True,
        )

    async def _maybe_build_alert_message(
        self, updated_daily: Optional[dict], now_utc: datetime.datetime
    ) -> Optional[str]:
        if not updated_daily:
            return None
        current_level = int(updated_daily.get("alert_level", 0))
        current_cost = float(updated_daily.get("cost_reserved_usd", 0.0))
        new_level = 0
        for idx, threshold in enumerate(self._alert_thresholds, start=1):
            if current_cost >= threshold:
                new_level = idx
        if new_level <= current_level:
            return None
        day_key = str(updated_daily["_id"])
        update_result = await self.trial_daily_usage.update_one(
            {"_id": day_key, "alert_level": current_level},
            {"$set": {"alert_level": new_level, "last_alert_at": now_utc}},
        )
        if int(getattr(update_result, "modified_count", 0)) == 0:
            return None
        cap = float(self.settings.trial_global_cost_usd_per_day)
        return f"Trial spend alert UTC day {day_key}: ${current_cost:.2f} / ${cap:.2f}"
