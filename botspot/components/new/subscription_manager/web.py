"""aiohttp webhook routes the host app mounts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from botspot.components.new.subscription_manager.settings import (
    STRIPE_WEBHOOK_PATH,
    YOOKASSA_WEBHOOK_PATH,
)

if TYPE_CHECKING:
    from aiohttp import web

    from botspot.components.new.subscription_manager.manager import SubscriptionManager


def aiohttp_routes(manager: SubscriptionManager) -> list:
    """Return aiohttp route defs for Stripe and YooKassa webhooks."""
    from aiohttp import web

    async def stripe_webhook(request: web.Request) -> web.Response:
        raw_body = await request.read()
        signature = request.headers.get("Stripe-Signature", "")
        event = manager.verify_stripe_webhook(raw_body, signature)
        await manager.handle_stripe_event(event)
        return web.json_response({"ok": True})

    async def yookassa_webhook(request: web.Request) -> web.Response:
        event: dict[str, Any] = await request.json()
        await manager.handle_yookassa_event(event)
        return web.json_response({"ok": True})

    return [
        web.post(STRIPE_WEBHOOK_PATH, stripe_webhook),
        web.post(YOOKASSA_WEBHOOK_PATH, yookassa_webhook),
    ]
