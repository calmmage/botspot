"""Correlate each Telegram update, its handler, persistent logs and errors."""

from __future__ import annotations

import traceback
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import uuid4

from aiogram import BaseMiddleware, Dispatcher
from aiogram.dispatcher.event.bases import UNHANDLED, CancelHandler, SkipHandler
from aiogram.types import Update
from loguru import logger

from botspot.observability.client import request_context


class HandlerNameMiddleware(BaseMiddleware):
    """Remember the actual selected callback, including handlers in child routers."""

    async def __call__(self, handler, event, data):
        context = data.get("observability_context")
        selected = data.get("handler")
        if context is not None and selected is not None:
            callback = selected.callback
            module = getattr(callback, "__module__", type(callback).__module__)
            name = getattr(callback, "__qualname__", type(callback).__qualname__)
            context["handler"] = f"{module}.{name}"
        return await handler(event, data)


class ObservabilityMiddleware(BaseMiddleware):
    """Write exactly one event, while allowing aiogram's error handler to run."""

    def __init__(self, client: Any):
        self.client = client

    async def __call__(self, handler, event: Update, data):
        started_at = datetime.now(UTC)
        started = perf_counter()
        kind = event.event_type
        payload = event.event
        user = data.get("event_from_user") or getattr(payload, "from_user", None)
        chat = data.get("event_chat") or getattr(payload, "chat", None)
        if chat is None:
            chat = getattr(getattr(payload, "message", None), "chat", None)
        context = {
            "request_id": uuid4().hex,
            "user_id": getattr(user, "id", None),
            "chat_id": getattr(chat, "id", None),
            "user": getattr(user, "username", None),
            "handler": None,
            "update_id": event.update_id,
            "kind": kind,
        }
        data["observability_context"] = context
        token = request_context.set(context)
        outcome, error_type = "ignored", None
        try:
            with logger.contextualize(**context):
                try:
                    result = await handler(event, data)
                    outcome = "ignored" if result is UNHANDLED else "ok"
                    return result
                except (SkipHandler, CancelHandler):
                    raise
                except Exception as error:
                    outcome, error_type = "error", type(error).__name__
                    await self.client.record_error(
                        **context,
                        error_type=error_type,
                        error_message=str(error),
                        traceback="".join(traceback.format_exception(error)),
                    )
                    raise
        finally:
            try:
                await self.client.record_event(
                    **context,
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                    latency_ms=round((perf_counter() - started) * 1000, 3),
                    outcome=outcome,
                    error_type=error_type,
                )
            finally:
                request_context.reset(token)


def setup_dispatcher(dp: Dispatcher, client: Any) -> None:
    """Install after built-in ErrorsMiddleware, before component middleware."""
    dp.update.outer_middleware(ObservabilityMiddleware(client))
    capture = HandlerNameMiddleware()
    for kind, observer in dp.observers.items():
        if kind not in {"update", "error"}:
            observer.middleware(capture)
