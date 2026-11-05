"""Plan errors and the OpenAI error -> exception mapping table.

Host bots fall back to their own paid path on ``PlanUsageCapped``,
``PlanNeedsRelink`` and ``PlanUnavailable``.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

from botspot.core.errors import BotspotError


class PlanError(BotspotError):
    """Base for chatgpt_plan errors. ``code`` is the OpenAI error code, if any."""

    def __init__(self, message: str, *, code: str = "", report_to_dev: bool = False):
        super().__init__(message, report_to_dev=report_to_dev)
        self.args = (message,)
        self.code = code


class PlanDisabled(PlanError):
    """The component flag is off. Raised before any I/O."""

    def __init__(self, message: str = "chatgpt_plan is disabled"):
        super().__init__(message)


class PlanNotLinked(PlanError):
    """The user has not linked a ChatGPT plan."""

    def __init__(self, message: str = "no ChatGPT plan linked"):
        super().__init__(message)


class PlanNeedsRelink(PlanError):
    """Tokens are revoked/expired; the user must link again."""


class PlanUsageCapped(PlanError):
    """The user hit their weekly per-app cap (ChatGPT settings -> Usage)."""

    def __init__(self, message: str, *, reset_hint: Optional[str] = None, code: str = ""):
        super().__init__(message, code=code)
        self.reset_hint = reset_hint


class PlanUnavailable(PlanError):
    """Plan inference is unavailable. ``retryable`` is False for 403 policy/region."""

    def __init__(self, message: str, *, code: str = "", retryable: bool = True):
        super().__init__(message, code=code)
        self.retryable = retryable


class PlanUnsupported(PlanError):
    """The plan path rejected a request param (named in ``param``)."""

    def __init__(self, message: str, *, param: Optional[str] = None, code: str = ""):
        super().__init__(message, code=code)
        self.param = param


class PlanLinkError(PlanError):
    """The link flow failed: bad/expired state, missing scope, failed code exchange."""


def _error_fields(body: Any) -> tuple[str, str, Optional[str]]:
    """Return (code, message, param) from an API (`{"error": {...}}`) or OAuth body."""
    if not isinstance(body, Mapping):
        return "", "", None
    err = body.get("error")
    if isinstance(err, Mapping):
        code = str(err.get("code") or err.get("type") or "")
        return code, str(err.get("message") or ""), err.get("param")
    # OAuth token endpoint shape: {"error": "invalid_grant", "error_description": "..."}
    return str(err or ""), str(body.get("error_description") or ""), None


def _reset_hint(body: Any, headers: Mapping[str, str]) -> Optional[str]:
    err = body.get("error") if isinstance(body, Mapping) else None
    if isinstance(err, Mapping) and err.get("resets_at"):
        return str(err["resets_at"])
    return headers.get("retry-after") or headers.get("Retry-After")


def _capped(msg: str, code: str, param, hint) -> PlanError:
    return PlanUsageCapped(msg or "ChatGPT plan usage cap reached", reset_hint=hint, code=code)


def _relink(msg: str, code: str, param, hint) -> PlanError:
    return PlanNeedsRelink(msg or "ChatGPT link expired, relink needed", code=code)


def _unavailable(msg: str, code: str, param, hint) -> PlanError:
    return PlanUnavailable(msg or "ChatGPT plan unavailable", code=code)


def _forbidden(msg: str, code: str, param, hint) -> PlanError:
    return PlanUnavailable(
        msg or "ChatGPT plan refused (policy/region)", code=code, retryable=False
    )


def _unsupported(msg: str, code: str, param, hint) -> PlanError:
    return PlanUnsupported(msg or f"unsupported param: {param}", param=param, code=code)


_Factory = Callable[[str, str, Optional[str], Optional[str]], PlanError]

# Error code -> exception. Codes win over HTTP status.
CODE_ERRORS: dict[str, _Factory] = {
    "subscription_sharing_usage_limit_exceeded": _capped,
    "subscription_sharing_usage_unavailable": _unavailable,
    "subscription_sharing_unsupported_capability": _unsupported,
    "invalid_grant": _relink,
    "invalid_refresh_token": _relink,
    "token_expired": _relink,
}

# HTTP status -> exception, when the code is unknown (401 also covers revoked tokens).
STATUS_ERRORS: dict[int, _Factory] = {
    401: _relink,
    403: _forbidden,
    429: _capped,
    503: _unavailable,
}


def error_from_response(
    status: int, body: Any, headers: Optional[Mapping[str, str]] = None
) -> PlanError:
    """Map an OpenAI error response (or stream error event) to a ``PlanError``."""
    code, message, param = _error_fields(body)
    hint = _reset_hint(body, headers or {})
    factory = CODE_ERRORS.get(code) or STATUS_ERRORS.get(status) or _unavailable
    return factory(message, code, param, hint)


__all__ = [
    "PlanError",
    "PlanDisabled",
    "PlanNotLinked",
    "PlanNeedsRelink",
    "PlanUsageCapped",
    "PlanUnavailable",
    "PlanUnsupported",
    "PlanLinkError",
    "CODE_ERRORS",
    "STATUS_ERRORS",
    "error_from_response",
]
