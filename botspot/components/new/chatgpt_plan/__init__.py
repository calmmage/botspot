"""botspot chatgpt_plan component: users fund LLM calls with their own ChatGPT plan.

"Sign in with ChatGPT" (OAuth 2 + PKCE) links a Telegram user to their ChatGPT plan;
``respond`` then runs on the Responses API with the user's token. Off by default
(``BOTSPOT_CHATGPT_PLAN_ENABLED``); with the flag off every call raises
``PlanDisabled`` and does no I/O. Needs an OpenAI-issued client ID (see README.md).
"""

from __future__ import annotations

from typing import Any, Optional

from botspot.components.new.chatgpt_plan.client import PlanResponse, ResponseInput
from botspot.components.new.chatgpt_plan.errors import (
    PlanDisabled,
    PlanError,
    PlanLinkError,
    PlanNeedsRelink,
    PlanNotLinked,
    PlanUnavailable,
    PlanUnsupported,
    PlanUsageCapped,
)
from botspot.components.new.chatgpt_plan.oauth import LinkResult
from botspot.components.new.chatgpt_plan.plan import ChatgptPlan
from botspot.components.new.chatgpt_plan.settings import ChatgptPlanSettings
from botspot.components.new.chatgpt_plan.store import PlanLink
from botspot.components.new.chatgpt_plan.web import aiohttp_routes, make_callback_handler
from botspot.utils.internal import get_logger

logger = get_logger()


def initialize(settings: ChatgptPlanSettings) -> ChatgptPlan:
    """Initialize the component. Requires mongo_database, client_id and an encryption key."""
    from botspot.core.dependency_manager import get_dependency_manager
    from botspot.core.errors import ConfigurationError

    deps = get_dependency_manager()
    if not deps.botspot_settings.mongo_database.enabled:
        raise ConfigurationError(
            "MongoDB is required for chatgpt_plan. Set BOTSPOT_MONGO_DATABASE_ENABLED=true."
        )
    if not settings.client_id or not settings.redirect_uri:
        raise ConfigurationError(
            "chatgpt_plan needs BOTSPOT_CHATGPT_PLAN_CLIENT_ID and _REDIRECT_URI "
            "(client ID is issued by OpenAI to approved partners)."
        )
    from botspot.components.data.mongo_database import get_database

    plan = ChatgptPlan(settings, db=get_database())
    logger.info("chatgpt_plan initialized")
    return plan


def get_chatgpt_plan() -> ChatgptPlan:
    """The initialized component. Raises ``PlanDisabled`` when the flag is off."""
    from botspot.core.dependency_manager import DependencyManager

    if not DependencyManager.is_initialized():
        raise PlanDisabled()
    plan = DependencyManager().chatgpt_plan
    if plan is None or not plan.settings.enabled:
        raise PlanDisabled()
    return plan


async def start_link(user_id: int) -> str:
    """Return the "Sign in with ChatGPT" URL for this Telegram user."""
    return await get_chatgpt_plan().start_link(user_id)


async def complete_link(state: str, code: str) -> LinkResult:
    """Finish the link from the OAuth callback (``state`` is single use)."""
    return await get_chatgpt_plan().complete_link(state, code)


async def get_access_token(user_id: int) -> str:
    """A valid access token for the user, refreshed when near expiry."""
    return await get_chatgpt_plan().get_access_token(user_id)


async def get_link(user_id: int) -> Optional[PlanLink]:
    """Link state (no tokens) for /settings, or None."""
    return await get_chatgpt_plan().get_link(user_id)


async def unlink(user_id: int) -> bool:
    """Forget the user's tokens. True if a link existed."""
    return await get_chatgpt_plan().unlink(user_id)


async def respond(
    user_id: int,
    model: str,
    input: ResponseInput,
    *,
    instructions: Optional[str] = None,
    **params: Any,
) -> PlanResponse:
    """Run one Responses call on the user's plan (``store=False``, ``stream=True``)."""
    return await get_chatgpt_plan().respond(
        user_id, model, input, instructions=instructions, **params
    )


async def list_models(user_id: int) -> list[str]:
    """Model ids available on the user's plan."""
    return await get_chatgpt_plan().list_models(user_id)


__all__ = [
    "ChatgptPlanSettings",
    "ChatgptPlan",
    "LinkResult",
    "PlanLink",
    "PlanResponse",
    "PlanError",
    "PlanDisabled",
    "PlanNotLinked",
    "PlanNeedsRelink",
    "PlanUsageCapped",
    "PlanUnavailable",
    "PlanUnsupported",
    "PlanLinkError",
    "initialize",
    "get_chatgpt_plan",
    "start_link",
    "complete_link",
    "get_access_token",
    "get_link",
    "unlink",
    "respond",
    "list_models",
    "aiohttp_routes",
    "make_callback_handler",
]
