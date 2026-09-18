"""
Simple LLM provider availability checker.
"""

import os
from typing import List, Optional, Sequence

# Provider to API key mapping
PROVIDER_API_KEYS = {
    "openai": ["OPENAI_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "google": ["GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_AI_API_KEY"],
    "xai": ["XAI_API_KEY"],
    "openrouter": ["OPENROUTER_API_KEY"],
}

# Simple default models for each provider
DEFAULT_MODELS = {
    "anthropic": "claude-4",
    "openai": "gpt-4o",
    "google": "gemini-2.5-pro",
    "xai": "grok-3",
    "openrouter": "openrouter/openai/gpt-4o",
}

_RETRYABLE_MARKERS = (
    "timeout",
    "timed out",
    "connection",
    "429",
    "rate limit",
    "ratelimit",
    "500",
    "502",
    "503",
    "504",
    "529",
    "overloaded",
    "unavailable",
    "credit",
    "quota",
    "insufficient",
    "balance",
)


def get_available_providers() -> List[str]:
    """
    Check which LLM providers have API keys available.

    Returns:
        List of available provider names
    """
    available = []

    for provider, key_names in PROVIDER_API_KEYS.items():
        for key_name in key_names:
            if os.getenv(key_name):
                available.append(provider)
                break

    return available


def provider_for_model(model: Optional[str]) -> Optional[str]:
    """Best-effort provider name from a model id or shortcut."""
    if not model:
        return None
    name = model.lower()
    if name.startswith("openrouter/") or name.startswith("openrouter."):
        return "openrouter"
    if "claude" in name or name.startswith("anthropic/"):
        return "anthropic"
    if "gemini" in name or name.startswith("gemini/") or name.startswith("google/"):
        return "google"
    if "grok" in name or name.startswith("xai/"):
        return "xai"
    if (
        name.startswith("openai/")
        or name.startswith("gpt-")
        or name.startswith("o1")
        or name.startswith("o3")
        or name.startswith("o4")
    ):
        return "openai"
    return None


def get_fallback_model(exclude_providers: Optional[Sequence[str]] = None) -> Optional[str]:
    """
    Get a model from any available provider.

    Args:
        exclude_providers: Providers that just failed (timeout, credits, etc.)

    Returns:
        Model name or None if no providers available
    """
    skip = {p.lower() for p in (exclude_providers or []) if p}
    available = [p for p in get_available_providers() if p not in skip]
    if not available:
        return None

    # Prefer anthropic, then openai, then others — unless that provider just failed
    for preferred in ["anthropic", "openai", "google", "xai", "openrouter"]:
        if preferred in available:
            return DEFAULT_MODELS[preferred]

    # Fallback to first available
    return DEFAULT_MODELS.get(available[0])


def is_api_key_error(error: Exception) -> bool:
    """
    Check if an error is related to API key issues.

    Args:
        error: Exception to check

    Returns:
        True if this looks like an API key error
    """
    error_str = str(error).lower()
    api_key_indicators = [
        "api key",
        "api_key",
        "authentication",
        "unauthorized",
        "invalid key",
        "missing key",
        "401",
        "403",
        "credit",
        "quota",
        "insufficient",
        "balance is too low",
    ]

    return any(indicator in error_str for indicator in api_key_indicators)


def is_retryable_llm_error(error: Exception) -> bool:
    """Timeouts, rate limits, credits, and auth failures are worth a different model."""
    if is_api_key_error(error):
        return True
    error_str = str(error).lower()
    return any(marker in error_str for marker in _RETRYABLE_MARKERS)
