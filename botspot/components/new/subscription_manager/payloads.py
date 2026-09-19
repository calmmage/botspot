"""Invoice payload signing (whisper PAYLOAD_PREFIX scheme)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Any, Optional

from pydantic import SecretStr

from botspot.components.new.subscription_manager.settings import (
    PAYLOAD_CODE_PROVIDERS,
    PAYLOAD_PREFIX,
    PAYLOAD_PROVIDER_CODES,
    PAYLOAD_SIGNATURE_BYTES,
    SubscriptionManagerSettings,
)
from botspot.core.errors import SubscriptionValidationError


def secret_to_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    if hasattr(value, "get_secret_value"):
        return str(value.get_secret_value())
    return str(value)


def signature_secret(settings: SubscriptionManagerSettings) -> str:
    explicit = secret_to_str(settings.signature_secret)
    if explicit:
        return explicit
    token = os.getenv("TELEGRAM_BOT_TOKEN") or ""
    if token:
        return token
    raise SubscriptionValidationError(
        "BOTSPOT_SUBSCRIPTION_MANAGER_SIGNATURE_SECRET or TELEGRAM_BOT_TOKEN is required."
    )


def payload_provider_code(provider: str) -> str:
    try:
        return PAYLOAD_PROVIDER_CODES[provider]
    except KeyError as e:
        raise SubscriptionValidationError(f"Unknown invoice provider: {provider}") from e


def payload_provider_from_code(provider_code: str) -> str:
    try:
        return PAYLOAD_CODE_PROVIDERS[provider_code]
    except KeyError as e:
        raise SubscriptionValidationError("Unknown invoice provider.") from e


def sign_invoice_payload(
    settings: SubscriptionManagerSettings, provider: str, invoice_id: str, telegram_user_id: int
) -> str:
    body = f"{provider}:{invoice_id}:{int(telegram_user_id)}"
    digest = hmac.new(signature_secret(settings).encode(), body.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest[:PAYLOAD_SIGNATURE_BYTES]).decode().rstrip("=")


def verify_invoice_payload(
    settings: SubscriptionManagerSettings,
    provider: str,
    invoice_id: str,
    telegram_user_id: int,
    signature: str,
) -> bool:
    expected = sign_invoice_payload(settings, provider, invoice_id, telegram_user_id)
    return hmac.compare_digest(expected, signature)


def sign_invoice_metadata(
    settings: SubscriptionManagerSettings, invoice_id: str, telegram_user_id: int
) -> str:
    body = f"{invoice_id}:{int(telegram_user_id)}"
    return hmac.new(signature_secret(settings).encode(), body.encode(), hashlib.sha256).hexdigest()


def verify_invoice_metadata(
    settings: SubscriptionManagerSettings, invoice_id: str, telegram_user_id: int, signature: str
) -> bool:
    expected = sign_invoice_metadata(settings, invoice_id, telegram_user_id)
    return hmac.compare_digest(expected, signature)


def build_invoice_payload(
    settings: SubscriptionManagerSettings, provider: str, invoice_id: str, telegram_user_id: int
) -> str:
    provider_code = payload_provider_code(provider)
    signature = sign_invoice_payload(settings, provider, invoice_id, telegram_user_id)
    return f"{PAYLOAD_PREFIX}:{provider_code}:{invoice_id}:{int(telegram_user_id)}:{signature}"


def parse_invoice_payload(
    settings: SubscriptionManagerSettings,
    payload: str,
    expected_provider: Optional[str] = None,
) -> dict[str, Any]:
    parts = payload.split(":")
    if len(parts) != 5:
        raise SubscriptionValidationError("Invalid invoice payload.")

    if parts[0] == PAYLOAD_PREFIX:
        _, provider_code, invoice_id, raw_user_id, signature = parts
        provider = payload_provider_from_code(provider_code)
        telegram_user_id = int(raw_user_id)
        if expected_provider and provider != expected_provider:
            raise SubscriptionValidationError("Invoice provider mismatch.")
        if not verify_invoice_payload(settings, provider, invoice_id, telegram_user_id, signature):
            raise SubscriptionValidationError("Invalid invoice payload signature.")
        return {
            "provider": provider,
            "invoice_id": invoice_id,
            "telegram_user_id": telegram_user_id,
        }

    if parts[0] != "billing":
        raise SubscriptionValidationError("Invalid invoice payload.")

    _, provider, invoice_id, raw_user_id, signature = parts
    if expected_provider and provider != expected_provider:
        raise SubscriptionValidationError("Invoice provider mismatch.")
    telegram_user_id = int(raw_user_id)
    if not verify_invoice_metadata(settings, invoice_id, telegram_user_id, signature):
        raise SubscriptionValidationError("Invalid invoice payload signature.")
    return {
        "provider": provider,
        "invoice_id": invoice_id,
        "telegram_user_id": telegram_user_id,
    }
