"""Mongo storage for pending OAuth states and linked plans. Tokens are Fernet-encrypted.

Never log token values: log user ids and statuses only.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Optional

from botspot.components.new.chatgpt_plan.errors import (
    PlanNeedsRelink,
    PlanNotLinked,
    PlanUsageCapped,
)
from botspot.components.new.chatgpt_plan.settings import (
    LINKS_COLLECTION,
    PENDING_COLLECTION,
    STATUS_ACTIVE,
    STATUS_CAPPED,
    STATUS_NEEDS_RELINK,
    ChatgptPlanSettings,
)
from botspot.core.errors import ConfigurationError
from botspot.utils.internal import get_logger

if TYPE_CHECKING:
    from botspot.components.new.chatgpt_plan.oauth import OAuthClient, TokenSet

logger = get_logger()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Mongo returns naive datetimes unless tz_aware; treat them as UTC."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


class TokenCipher:
    """Fernet wrapper. ``cryptography`` is imported lazily."""

    def __init__(self, key: str):
        if not key:
            raise ConfigurationError(
                "BOTSPOT_CHATGPT_PLAN_TOKEN_ENCRYPTION_KEY is required (a Fernet key)."
            )
        from cryptography.fernet import Fernet

        self._fernet = Fernet(key.encode())

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        return self._fernet.decrypt(value.encode()).decode()


@dataclass
class PlanLink:
    """A user's link, without tokens. Safe to show in /settings."""

    user_id: int
    status: str
    sub: str = ""
    email: str = ""
    scopes: str = ""
    linked_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    capped_until: Optional[datetime] = None


class LinkStore:
    def __init__(self, settings: ChatgptPlanSettings, db: Any, cipher: TokenCipher):
        self.settings = settings
        self.pending = db[PENDING_COLLECTION]
        self.links = db[LINKS_COLLECTION]
        self.cipher = cipher
        self._refresh_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._indexes_ready = False

    async def ensure_indexes(self) -> None:
        if self._indexes_ready:
            return
        await self.pending.create_index("expires_at", expireAfterSeconds=0)
        self._indexes_ready = True

    # -- pending OAuth states ------------------------------------------------

    async def save_pending(self, state: str, user_id: int, verifier: str, nonce: str) -> None:
        await self.ensure_indexes()
        now = utcnow()
        await self.pending.insert_one(
            {
                "_id": state,
                "user_id": user_id,
                "code_verifier": self.cipher.encrypt(verifier),
                "nonce": nonce,
                "created_at": now,
                "expires_at": now + timedelta(seconds=self.settings.pending_ttl_seconds),
            }
        )

    async def pop_pending(self, state: str) -> Optional[dict]:
        """Single use: the record is deleted on read. Expired records return None."""
        doc = await self.pending.find_one_and_delete({"_id": state})
        expires_at = as_utc(doc.get("expires_at")) if doc else None
        if doc is None or expires_at is None or expires_at <= utcnow():
            return None
        doc["code_verifier"] = self.cipher.decrypt(doc["code_verifier"])
        return doc

    # -- links ----------------------------------------------------------------

    async def save_link(self, user_id: int, tokens: TokenSet, sub: str, email: str) -> None:
        now = utcnow()
        await self.links.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "sub": sub,
                    "email": email,
                    "client_id": self.settings.client_id,
                    "scopes": tokens.scope,
                    "status": STATUS_ACTIVE,
                    "capped_until": None,
                    "linked_at": now,
                    **self._token_fields(tokens),
                }
            },
            upsert=True,
        )
        logger.info(f"chatgpt_plan: user {user_id} linked")

    def _token_fields(self, tokens: TokenSet) -> dict:
        fields: dict[str, Any] = {
            "access_token": self.cipher.encrypt(tokens.access_token),
            "expires_at": utcnow() + timedelta(seconds=tokens.expires_in),
        }
        if tokens.refresh_token:  # rolling: keep the old one if none is returned
            fields["refresh_token"] = self.cipher.encrypt(tokens.refresh_token)
        return fields

    async def get_link(self, user_id: int) -> Optional[PlanLink]:
        doc = await self.links.find_one({"_id": user_id})
        if doc is None:
            return None
        return PlanLink(
            user_id=user_id,
            status=doc.get("status", STATUS_ACTIVE),
            sub=doc.get("sub", ""),
            email=doc.get("email", ""),
            scopes=doc.get("scopes", ""),
            linked_at=as_utc(doc.get("linked_at")),
            last_used_at=as_utc(doc.get("last_used_at")),
            capped_until=as_utc(doc.get("capped_until")),
        )

    async def unlink(self, user_id: int) -> bool:
        result = await self.links.delete_one({"_id": user_id})
        logger.info(f"chatgpt_plan: user {user_id} unlinked")
        return bool(result.deleted_count)

    async def mark_needs_relink(self, user_id: int) -> None:
        await self.links.update_one(
            {"_id": user_id},
            {
                "$set": {"status": STATUS_NEEDS_RELINK},
                "$unset": {"access_token": "", "refresh_token": "", "expires_at": ""},
            },
        )
        logger.info(f"chatgpt_plan: user {user_id} needs relink")

    async def mark_capped(self, user_id: int, error: PlanUsageCapped) -> None:
        until = utcnow() + timedelta(seconds=self.settings.cap_pause_seconds)
        hint = error.reset_hint or ""
        if hint.isdigit():  # Retry-After seconds
            until = utcnow() + timedelta(seconds=int(hint))
        await self.links.update_one(
            {"_id": user_id}, {"$set": {"status": STATUS_CAPPED, "capped_until": until}}
        )
        logger.info(f"chatgpt_plan: user {user_id} capped until {until.isoformat()}")

    async def touch(self, user_id: int) -> None:
        await self.links.update_one({"_id": user_id}, {"$set": {"last_used_at": utcnow()}})

    # -- access tokens --------------------------------------------------------

    async def _usable_doc(self, user_id: int) -> dict:
        doc = await self.links.find_one({"_id": user_id})
        if doc is None:
            raise PlanNotLinked()
        status = doc.get("status", STATUS_ACTIVE)
        if status == STATUS_NEEDS_RELINK or not doc.get("refresh_token"):
            raise PlanNeedsRelink("ChatGPT link expired, relink needed")
        capped_until = as_utc(doc.get("capped_until"))
        if status == STATUS_CAPPED and capped_until and capped_until > utcnow():
            raise PlanUsageCapped("ChatGPT plan usage cap reached", reset_hint=str(capped_until))
        return doc

    def _fresh_access_token(self, doc: dict) -> Optional[str]:
        expires_at = as_utc(doc.get("expires_at"))
        margin = timedelta(seconds=self.settings.refresh_margin_seconds)
        if doc.get("access_token") and expires_at and expires_at - margin > utcnow():
            return self.cipher.decrypt(doc["access_token"])
        return None

    async def get_access_token(self, user_id: int, oauth: OAuthClient) -> str:
        """Return a valid access token, refreshing when within the margin."""
        async with self._refresh_locks[user_id]:
            doc = await self._usable_doc(user_id)
            token = self._fresh_access_token(doc)
            if token is not None:
                return token
            try:
                tokens = await oauth.refresh(self.cipher.decrypt(doc["refresh_token"]))
            except PlanNeedsRelink:
                await self.mark_needs_relink(user_id)
                raise
            await self.links.update_one(
                {"_id": user_id},
                {
                    "$set": {
                        "status": STATUS_ACTIVE,
                        "capped_until": None,
                        **self._token_fields(tokens),
                    }
                },
            )
            logger.debug(f"chatgpt_plan: refreshed token for user {user_id}")
            return tokens.access_token
