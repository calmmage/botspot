"""Dispatcher-free Mongo writers shared by botspot and other Python bots."""

from __future__ import annotations

import asyncio
import re
import sys
import traceback
from collections.abc import Mapping
from contextvars import ContextVar
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any
from uuid import uuid4

request_context: ContextVar[Mapping[str, Any]] = ContextVar(
    "botspot_request", default=MappingProxyType({})
)
_SECRET_KEY = re.compile(
    r"token|secret|password|authorization|api[_-]?key|cookie|initdata", re.IGNORECASE
)
_TOKEN = re.compile(
    r"\b\d{5,}:[A-Za-z0-9_-]{15,}\b|\b(?:sk|ghp|github_pat)[-_][A-Za-z0-9_-]{12,}\b"
)
_ASSIGNMENT = re.compile(
    r"(?i)((?:[\w-]*(?:token|secret|password|api[_-]?key)[\w-]*|authorization|cookie)"
    r"[\"']?\s*[:=]\s*[\"']?)(?:Bearer\s+)?[^\s,;\"'}]+"
)
_URL = re.compile(r"(?:https?|mongodb(?:\+srv)?)://[^\s<>\"']+")


def redact(value: Any, secrets: tuple[str, ...] = ()) -> Any:
    """Strip credential fields, known secrets, URI credentials and URL query strings."""
    if isinstance(value, dict):
        return {
            str(k): "[REDACTED]" if _SECRET_KEY.search(str(k)) else redact(v, secrets)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(v, secrets) for v in value]
    if not isinstance(value, str):
        return value
    for secret in secrets:
        if secret:
            value = value.replace(secret, "[REDACTED]")
    value = _TOKEN.sub("[REDACTED]", value)
    value = _ASSIGNMENT.sub(r"\1[REDACTED]", value)

    def clean_url(match):
        scheme, rest = match.group().split("://", 1)
        authority, slash, tail = rest.partition("/")
        authority = authority.rsplit("@", 1)[-1]
        clean = authority + slash + tail
        clean = clean.split("#", 1)[0]
        return scheme + "://" + clean.split("?", 1)[0] + ("?[REDACTED]" if "?" in clean else "")

    return _URL.sub(clean_url, value)


class ObservabilityClient:
    """Async PyMongo-compatible writer. Database objects can also be in-memory test doubles.

    Storage failure handling lives at this single telemetry boundary. A database outage must
    neither replace the application's exception nor prevent its normal error reporting.
    """

    def __init__(
        self,
        database: Any,
        bot_name: str,
        *,
        registry_database: Any = None,
        metrics: tuple[str, ...] = ("cost",),
        dimensions: tuple[str, ...] = (),
        secrets: tuple[str, ...] = (),
    ):
        self.database = database
        self.registry_database = registry_database if registry_database is not None else database
        self.bot_name = bot_name
        self.metrics = metrics
        self.dimensions = dimensions
        self.secrets = secrets
        self.failed_writes = 0
        self._mongo_client = None

    @classmethod
    def from_url(cls, mongo_url: str, bot_name: str, database: str = "botspot", **kwargs):
        """Create a client without aiogram, a bot token or a dispatcher."""
        from pymongo import AsyncMongoClient

        mongo = AsyncMongoClient(mongo_url, serverSelectionTimeoutMS=2000)
        instance = cls(mongo[database], bot_name, **kwargs)
        instance._mongo_client = mongo
        return instance

    async def close(self):
        if self._mongo_client is not None:
            await self._mongo_client.close()

    async def _write(self, collection: str, fields: dict, *, key: dict | None = None):
        now = datetime.now(UTC)
        doc = redact({**request_context.get(), **fields, "bot": self.bot_name}, self.secrets)
        doc.setdefault("time", now)

        async def write():
            if key is None:
                await self.database[collection].insert_one(doc)
            else:
                await self.database[collection].update_one(key, {"$set": doc}, upsert=True)

        await self.run_safely(write(), "write")

    async def run_safely(self, operation, label: str) -> bool:
        """Single failure boundary for optional telemetry I/O, including its lifecycle."""
        try:
            async with asyncio.timeout(3):
                await operation
            return True
        except Exception as error:  # noqa: BLE001 - central optional telemetry failure boundary
            self.failed_writes += 1
            # Never feed failures back through loguru's Mongo sink or print credentials.
            print(f"botspot telemetry {label} unavailable: {type(error).__name__}", file=sys.stderr)
            return False

    async def ensure_indexes(self, retention_days: int = 30):
        """Create TTL and compound indexes matching dashboard filters once at startup."""
        for collection in ("botspot_logs", "botspot_events", "botspot_errors", "botspot_usage"):
            if collection == "botspot_logs":
                await self.database[collection].create_index(
                    "time", expireAfterSeconds=retention_days * 86400, name="retention"
                )
            await self.database[collection].create_index([("bot", 1), ("time", -1)])
            await self.database[collection].create_index(
                [("bot", 1), ("request_id", 1), ("time", -1)]
            )
            await self.database[collection].create_index([("bot", 1), ("user_id", 1), ("time", -1)])
        await self.database["botspot_logs"].create_index([("bot", 1), ("level", 1), ("time", -1)])
        await self.database["botspot_events"].create_index([("bot", 1), ("started_at", -1)])
        await self.database["botspot_errors"].create_index(
            [("bot", 1), ("request_id", 1)], unique=True
        )
        await self.database["botspot_bot_registry"].create_index("bot_id", unique=True)
        if self.registry_database is not self.database:
            await self.registry_database["botspot_bot_registry"].create_index("bot_id", unique=True)
        await self.registry_database["botspot_bot_registry"].create_index("owners")

    async def record_event(self, **fields):
        now = datetime.now(UTC)
        fields.setdefault("started_at", fields.get("time", now))
        fields.setdefault("finished_at", now)
        fields.setdefault(
            "latency_ms", (fields["finished_at"] - fields["started_at"]).total_seconds() * 1000
        )
        fields.setdefault("kind", "event")
        fields.setdefault("outcome", "ok")
        fields.setdefault("request_id", request_context.get().get("request_id") or uuid4().hex)
        await self._write("botspot_events", fields)

    async def record_usage(self, kind: str, **fields):
        await self._write("botspot_usage", {**fields, "kind": kind})

    async def record_error(self, **fields):
        request_id = (
            fields.get("request_id") or request_context.get().get("request_id") or uuid4().hex
        )
        fields.setdefault("created_at", datetime.now(UTC))
        await self._write(
            "botspot_errors",
            {**fields, "request_id": request_id},
            key={"bot": self.bot_name, "request_id": request_id},
        )

    async def sink(self, message):
        """Loguru coroutine sink; use logger.add(client.sink, level='INFO', loop=loop)."""
        record = message.record
        if record["level"].no < 20:
            return
        exception = record["exception"]
        exception_text = "".join(traceback.format_exception(*exception)) if exception else None
        await self._write(
            "botspot_logs",
            {
                **record["extra"],
                "time": record["time"],
                "level": record["level"].name,
                "logger": record["name"],
                "message": record["message"],
                "exception": exception_text,
            },
        )


def log_sink(mongo_url: str, bot_name: str, database: str = "botspot", **kwargs):
    """Return a Loguru async sink. Its ``__self__`` owns indexes and close lifecycle."""
    return ObservabilityClient.from_url(mongo_url, bot_name, database, **kwargs).sink


async def record_event(client: ObservabilityClient, **fields):
    await client.record_event(**fields)


async def record_usage(client: ObservabilityClient, kind: str, **fields):
    await client.record_usage(kind, **fields)
