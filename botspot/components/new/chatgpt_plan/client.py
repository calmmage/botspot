"""Plan-funded inference: Responses API only, ``store=False`` + ``stream=True``."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional, Union

from botspot.components.new.chatgpt_plan.errors import (
    PlanNeedsRelink,
    PlanUnavailable,
    PlanUnsupported,
    PlanUsageCapped,
    error_from_response,
)
from botspot.components.new.chatgpt_plan.settings import (
    DISALLOWED_PARAMS,
    REQUIRED_PARAMS,
    ChatgptPlanSettings,
)
from botspot.utils.internal import get_logger

if TYPE_CHECKING:
    from botspot.components.new.chatgpt_plan.http import HttpResult, Transport
    from botspot.components.new.chatgpt_plan.oauth import OAuthClient
    from botspot.components.new.chatgpt_plan.store import LinkStore

logger = get_logger()

ResponseInput = Union[str, list[dict[str, Any]]]
MAX_PARAM_DROPS = 3


@dataclass
class PlanResponse:
    text: str
    model: str
    usage: dict = field(default_factory=dict)


def build_payload(
    model: str, input: ResponseInput, instructions: Optional[str], params: dict
) -> dict:
    """Build a Responses payload, stripping params the plan path rejects."""
    dropped = sorted(k for k in params if k in DISALLOWED_PARAMS)
    if dropped:
        logger.debug(f"chatgpt_plan: dropping unsupported params {dropped}")
    payload = {k: v for k, v in params.items() if k not in DISALLOWED_PARAMS}
    payload.update(model=model, input=input, store=False, stream=True)
    if instructions:
        payload["instructions"] = instructions
    return payload


def _output_text(response: dict) -> str:
    """Fallback: collect output_text parts from a completed response object."""
    parts = []
    for item in response.get("output") or []:
        for content in item.get("content") or []:
            if content.get("type") == "output_text":
                parts.append(content.get("text", ""))
    return "".join(parts)


def parse_stream(events: list[dict], requested_model: str) -> PlanResponse:
    """Accumulate output text. Success only after ``response.completed``."""
    deltas: list[str] = []
    for event in events:
        kind = event.get("type")
        if kind == "response.output_text.delta":
            deltas.append(event.get("delta", ""))
        elif kind in ("error", "response.failed"):
            body = event.get("response") or {"error": event.get("error") or event}
            raise error_from_response(200, body)
        elif kind == "response.completed":
            response = event.get("response") or {}
            return PlanResponse(
                text="".join(deltas) or _output_text(response),
                model=response.get("model") or requested_model,
                usage=response.get("usage") or {},
            )
    raise PlanUnavailable("stream ended without response.completed")


def drop_param(payload: dict, param: Optional[str]) -> bool:
    """Drop the param named by ``unsupported_capability``. False if it can't be dropped."""
    if not param or param in REQUIRED_PARAMS or param not in payload:
        return False
    del payload[param]
    logger.info(f"chatgpt_plan: dropped param '{param}' after unsupported_capability")
    return True


class ResponsesClient:
    def __init__(
        self,
        settings: ChatgptPlanSettings,
        transport: Transport,
        store: LinkStore,
        oauth: OAuthClient,
    ):
        self.settings = settings
        self.transport = transport
        self.store = store
        self.oauth = oauth

    def _url(self, path: str) -> str:
        return self.settings.api_base.rstrip("/") + path

    async def _check(self, user_id: int, result: HttpResult) -> None:
        if result.ok:
            return
        error = error_from_response(result.status, result.body, result.headers)
        await self._record(user_id, error)
        raise error

    async def _record(self, user_id: int, error: Exception) -> None:
        if isinstance(error, PlanNeedsRelink):
            await self.store.mark_needs_relink(user_id)
        elif isinstance(error, PlanUsageCapped):
            await self.store.mark_capped(user_id, error)

    async def _respond_once(self, user_id: int, payload: dict) -> PlanResponse:
        token = await self.store.get_access_token(user_id, self.oauth)
        result = await self.transport.post_sse(self._url("/responses"), token, payload)
        await self._check(user_id, result)
        try:
            return parse_stream(result.events, payload["model"])
        except (PlanNeedsRelink, PlanUsageCapped) as error:
            await self._record(user_id, error)
            raise

    async def _backoff(self, attempt: int, error: PlanUnavailable) -> None:
        if not error.retryable or attempt >= self.settings.unavailable_retries:
            raise error
        await asyncio.sleep(self.settings.unavailable_backoff_seconds * 2**attempt)

    async def respond(
        self,
        user_id: int,
        model: str,
        input: ResponseInput,
        *,
        instructions: Optional[str] = None,
        **params: Any,
    ) -> PlanResponse:
        payload = build_payload(model, input, instructions, params)
        unavailable = drops = 0
        while True:
            try:
                response = await self._respond_once(user_id, payload)
            except PlanUnsupported as error:
                drops += 1
                if drops > MAX_PARAM_DROPS or not drop_param(payload, error.param):
                    raise
                continue
            except PlanUnavailable as error:
                await self._backoff(unavailable, error)
                unavailable += 1
                continue
            await self.store.touch(user_id)
            return response

    async def list_models(self, user_id: int) -> list[str]:
        """Model ids from the user's catalog with ``visibility == "list"``."""
        token = await self.store.get_access_token(user_id, self.oauth)
        result = await self.transport.get_json(self._url("/models"), token)
        await self._check(user_id, result)
        models = (result.body or {}).get("data") or []
        return [m["id"] for m in models if m.get("visibility") == "list" and m.get("id")]
