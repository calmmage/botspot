"""Sign in with ChatGPT: OAuth 2 auth-code + PKCE (S256), OIDC id_token claims."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass
from typing import TYPE_CHECKING, Awaitable, Callable, Optional
from urllib.parse import urlencode

from botspot.components.new.chatgpt_plan.errors import (
    PlanLinkError,
    PlanUnavailable,
    error_from_response,
)
from botspot.components.new.chatgpt_plan.settings import REQUIRED_SCOPE, ChatgptPlanSettings
from botspot.utils.internal import get_logger

if TYPE_CHECKING:
    from botspot.components.new.chatgpt_plan.http import Transport
    from botspot.components.new.chatgpt_plan.store import LinkStore

logger = get_logger()

# (id_token, settings) -> None; raises PlanLinkError when the signature is invalid.
IdTokenVerifier = Callable[[str, ChatgptPlanSettings], Awaitable[None]]


@dataclass
class TokenSet:
    access_token: str
    expires_in: int
    refresh_token: str = ""
    id_token: str = ""
    scope: str = ""


@dataclass
class LinkResult:
    user_id: int
    sub: str
    email: str
    scopes: str


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, S256 code_challenge)."""
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge


def build_authorize_url(
    settings: ChatgptPlanSettings, *, state: str, nonce: str, code_challenge: str
) -> str:
    params = {
        "response_type": "code",
        "client_id": settings.client_id,
        "redirect_uri": settings.redirect_uri,
        "scope": settings.scopes,
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "resource": settings.resource,
    }
    if settings.agent_name_hint:
        params["agent_name_hint"] = settings.agent_name_hint
    return f"{settings.authorize_url}?{urlencode(params)}"


def decode_id_token_claims(id_token: str) -> dict:
    """Decode the JWT payload WITHOUT verifying its signature.

    The signature is checked separately by ``verify_id_token_signature``.
    """
    parts = id_token.split(".")
    if len(parts) != 3:
        raise PlanLinkError("malformed id_token")
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


async def verify_id_token_signature(id_token: str, settings: ChatgptPlanSettings) -> None:
    """TODO(siwc-client-id): verify the id_token signature against the issuer JWKS.

    NOT IMPLEMENTED. Until it is, we rely on the id_token arriving straight from the
    token endpoint over TLS (OIDC Core 3.1.3.7 allows this for the code flow) plus the
    iss / aud / nonce checks in ``_check_claims``. Implement once OpenAI issues a client
    ID and the JWKS URL / signing algs can be tested. Tests inject a verifier through
    ``OAuthClient(id_token_verifier=...)``.
    """
    logger.warning("chatgpt_plan: id_token signature NOT verified (JWKS TODO)")


def _check_claims(claims: dict, settings: ChatgptPlanSettings, nonce: str) -> None:
    aud = claims.get("aud")
    audiences = aud if isinstance(aud, list) else [aud]
    if claims.get("iss", "").rstrip("/") != settings.issuer.rstrip("/"):
        raise PlanLinkError("id_token issuer mismatch")
    if settings.client_id not in audiences:
        raise PlanLinkError("id_token audience mismatch")
    if claims.get("nonce") != nonce:
        raise PlanLinkError("id_token nonce mismatch")
    if not claims.get("sub"):
        raise PlanLinkError("id_token has no sub")


def _token_set(body: dict, requested_scope: str) -> TokenSet:
    if not body.get("access_token"):
        raise PlanUnavailable("token endpoint returned no access_token")
    return TokenSet(
        access_token=body["access_token"],
        expires_in=int(body.get("expires_in") or 3600),
        refresh_token=body.get("refresh_token") or "",
        id_token=body.get("id_token") or "",
        # RFC 6749 5.1: an omitted scope means "as requested".
        scope=body.get("scope") or requested_scope,
    )


class OAuthClient:
    def __init__(
        self,
        settings: ChatgptPlanSettings,
        transport: Transport,
        store: LinkStore,
        id_token_verifier: Optional[IdTokenVerifier] = None,
    ):
        self.settings = settings
        self.transport = transport
        self.store = store
        self.id_token_verifier = id_token_verifier or verify_id_token_signature

    async def start_link(self, user_id: int) -> str:
        """Create a single-use pending state and return the authorize URL."""
        verifier, challenge = pkce_pair()
        state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        await self.store.save_pending(state, user_id, verifier, nonce)
        logger.info(f"chatgpt_plan: link started for user {user_id}")
        return build_authorize_url(
            self.settings, state=state, nonce=nonce, code_challenge=challenge
        )

    async def complete_link(self, state: str, code: str) -> LinkResult:
        """Validate state, exchange the code, check scope + id_token, save the link."""
        pending = await self.store.pop_pending(state)
        if pending is None:
            raise PlanLinkError("unknown, used or expired link state")
        tokens = await self._exchange_code(code, pending["code_verifier"])
        if REQUIRED_SCOPE not in tokens.scope.split():
            raise PlanLinkError(f"granted scope lacks {REQUIRED_SCOPE}")
        if not tokens.refresh_token or not tokens.id_token:
            raise PlanLinkError("token response lacks refresh_token or id_token")
        await self.id_token_verifier(tokens.id_token, self.settings)
        claims = decode_id_token_claims(tokens.id_token)
        _check_claims(claims, self.settings, pending["nonce"])
        user_id = pending["user_id"]
        email = claims.get("email", "")
        await self.store.save_link(user_id, tokens, claims["sub"], email)
        return LinkResult(user_id=user_id, sub=claims["sub"], email=email, scopes=tokens.scope)

    async def _exchange_code(self, code: str, verifier: str) -> TokenSet:
        form = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.settings.redirect_uri,
            "client_id": self.settings.client_id,
            "code_verifier": verifier,
            "resource": self.settings.resource,
        }
        result = await self.transport.post_form(self.settings.token_url, form)
        if not result.ok:
            err = error_from_response(result.status, result.body, result.headers)
            raise PlanLinkError(f"code exchange failed: {err.code or result.status}")
        return _token_set(result.body or {}, self.settings.scopes)

    async def refresh(self, refresh_token: str) -> TokenSet:
        """Refresh grant. Raises ``PlanNeedsRelink`` on invalid_grant / 401."""
        form = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.settings.client_id,
            "resource": self.settings.resource,
        }
        result = await self.transport.post_form(self.settings.token_url, form)
        if not result.ok:
            raise error_from_response(result.status, result.body, result.headers)
        return _token_set(result.body or {}, self.settings.scopes)
