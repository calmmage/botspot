"""ChatgptPlan: the component object. Every method raises ``PlanDisabled`` before I/O
when the flag is off."""

from __future__ import annotations

from typing import Any, Optional

from botspot.components.new.chatgpt_plan.client import (
    PlanResponse,
    ResponseInput,
    ResponsesClient,
)
from botspot.components.new.chatgpt_plan.errors import PlanDisabled
from botspot.components.new.chatgpt_plan.http import AiohttpTransport, Transport
from botspot.components.new.chatgpt_plan.oauth import IdTokenVerifier, LinkResult, OAuthClient
from botspot.components.new.chatgpt_plan.settings import ChatgptPlanSettings
from botspot.components.new.chatgpt_plan.store import LinkStore, PlanLink, TokenCipher


class ChatgptPlan:
    def __init__(
        self,
        settings: ChatgptPlanSettings,
        *,
        db: Any,
        transport: Optional[Transport] = None,
        id_token_verifier: Optional[IdTokenVerifier] = None,
    ):
        self.settings = settings
        if not settings.enabled:
            return  # nothing is built: no cipher, no collections, no sessions
        transport = transport or AiohttpTransport(settings.request_timeout_seconds)
        key = settings.token_encryption_key
        cipher = TokenCipher(key.get_secret_value() if key else "")
        self.store = LinkStore(settings, db, cipher)
        self.oauth = OAuthClient(settings, transport, self.store, id_token_verifier)
        self.client = ResponsesClient(settings, transport, self.store, self.oauth)

    def _require_enabled(self) -> None:
        if not self.settings.enabled:
            raise PlanDisabled()

    async def start_link(self, user_id: int) -> str:
        self._require_enabled()
        return await self.oauth.start_link(user_id)

    async def complete_link(self, state: str, code: str) -> LinkResult:
        self._require_enabled()
        return await self.oauth.complete_link(state, code)

    async def get_access_token(self, user_id: int) -> str:
        self._require_enabled()
        return await self.store.get_access_token(user_id, self.oauth)

    async def get_link(self, user_id: int) -> Optional[PlanLink]:
        self._require_enabled()
        return await self.store.get_link(user_id)

    async def unlink(self, user_id: int) -> bool:
        self._require_enabled()
        return await self.store.unlink(user_id)

    async def respond(
        self,
        user_id: int,
        model: str,
        input: ResponseInput,
        *,
        instructions: Optional[str] = None,
        **params: Any,
    ) -> PlanResponse:
        self._require_enabled()
        return await self.client.respond(user_id, model, input, instructions=instructions, **params)

    async def list_models(self, user_id: int) -> list[str]:
        self._require_enabled()
        return await self.client.list_models(user_id)
