"""Settings for the chatgpt_plan component ("Sign in with ChatGPT")."""

from __future__ import annotations

from urllib.parse import urlparse

from pydantic import SecretStr
from pydantic_settings import BaseSettings

DEFAULT_SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
REQUIRED_SCOPE = "chatgpt.tokens.use.direct"
DEFAULT_CALLBACK_PATH = "/api/chatgpt/callback"

LINKS_COLLECTION = "chatgpt_links"
PENDING_COLLECTION = "chatgpt_oauth_pending"

STATUS_ACTIVE = "active"
STATUS_NEEDS_RELINK = "needs_relink"
STATUS_CAPPED = "capped"

# Plan-funded inference rejects these (Responses API, SIWC preview limitations).
DISALLOWED_PARAMS = frozenset(
    {
        "temperature",
        "top_p",
        "max_output_tokens",
        "max_tokens",
        "max_completion_tokens",
        "metadata",
        "user",
        "previous_response_id",
        "background",
        "tools",
        "tool_choice",
        "parallel_tool_calls",
    }
)
# Params the component sets itself; never dropped on `unsupported_capability`.
REQUIRED_PARAMS = frozenset({"model", "input", "store", "stream"})


class ChatgptPlanSettings(BaseSettings):
    """Env prefix ``BOTSPOT_CHATGPT_PLAN_``.

    Off by default. With ``ENABLED=false`` every call raises ``PlanDisabled`` and
    does no I/O. A client ID comes only from OpenAI partner approval, so every
    endpoint, scope and redirect stays configurable.
    """

    enabled: bool = False
    client_id: str = ""
    issuer: str = "https://auth.openai.com"
    authorize_path: str = "/api/accounts/authorize"
    token_path: str = "/api/accounts/oauth/token"
    resource: str = "https://api.openai.com/v1"
    api_base: str = "https://api.openai.com/v1"
    scopes: str = DEFAULT_SCOPES
    redirect_uri: str = ""  # our public HTTPS callback; partner value TBD
    agent_name_hint: str = ""  # sent on authorize only when set
    token_encryption_key: SecretStr | None = None  # Fernet key
    pending_ttl_seconds: int = 600
    refresh_margin_seconds: int = 300
    unavailable_retries: int = 2
    unavailable_backoff_seconds: float = 2.0
    cap_pause_seconds: int = 3600  # used when a 429 carries no reset hint
    request_timeout_seconds: float = 120.0
    return_url: str = ""  # optional "back to Telegram" link on the callback page

    @property
    def authorize_url(self) -> str:
        return self.issuer.rstrip("/") + self.authorize_path

    @property
    def token_url(self) -> str:
        return self.issuer.rstrip("/") + self.token_path

    @property
    def callback_path(self) -> str:
        return urlparse(self.redirect_uri).path or DEFAULT_CALLBACK_PATH

    class Config:
        env_prefix = "BOTSPOT_CHATGPT_PLAN_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
