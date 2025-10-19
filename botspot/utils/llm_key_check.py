"""
Simple LLM provider availability checker.
"""
import os
from typing import List, Optional

# Provider to API key mapping
PROVIDER_API_KEYS = {
    "openai": ["OPENAI_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"], 
    "google": ["GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_AI_API_KEY"],
    "xai": ["XAI_API_KEY"],
}

# Simple default models for each provider
DEFAULT_MODELS = {
    "anthropic": "claude-4",
    "openai": "gpt-4o", 
    "google": "gemini-2.5-pro",
    "xai": "grok-3",
}


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


def get_fallback_model() -> Optional[str]:
    """
    Get a model from any available provider.
    
    Returns:
        Model name or None if no providers available
    """
    available = get_available_providers()
    if not available:
        return None
    
    # Prefer anthropic, then openai, then others
    for preferred in ["anthropic", "openai", "google", "xai"]:
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
        "api key", "api_key", "authentication", "unauthorized", 
        "invalid key", "missing key", "401", "403"
    ]
    
    return any(indicator in error_str for indicator in api_key_indicators)