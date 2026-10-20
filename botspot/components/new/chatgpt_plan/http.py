"""Thin aiohttp transport. Tests swap it for a fake; nothing here logs headers or bodies."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Protocol


@dataclass
class HttpResult:
    status: int
    body: Any = None  # parsed JSON (or None)
    events: list[dict] = field(default_factory=list)  # parsed SSE events, 2xx streams only
    headers: Mapping[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


class Transport(Protocol):
    async def post_form(self, url: str, form: Mapping[str, str]) -> HttpResult: ...

    async def get_json(self, url: str, token: str) -> HttpResult: ...

    async def post_sse(self, url: str, token: str, payload: Mapping[str, Any]) -> HttpResult: ...


def parse_sse(lines: Iterable[str]) -> list[dict]:
    """Parse ``data:`` lines of a server-sent event stream into JSON events."""
    events: list[dict] = []
    data: list[str] = []
    for raw in list(lines) + [""]:
        line = raw.rstrip("\r\n")
        if line.startswith("data:"):
            data.append(line[5:].lstrip())
        elif not line and data:
            chunk = "\n".join(data)
            data = []
            if chunk != "[DONE]":
                events.append(json.loads(chunk))
    return events


def _json_or_none(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        return None


class AiohttpTransport:
    def __init__(self, timeout_seconds: float = 120.0):
        self.timeout_seconds = timeout_seconds

    def _session(self):
        import aiohttp

        return aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout_seconds))

    async def post_form(self, url: str, form: Mapping[str, str]) -> HttpResult:
        async with self._session() as session:
            async with session.post(url, data=dict(form)) as resp:
                text = await resp.text()
                return HttpResult(resp.status, _json_or_none(text), headers=dict(resp.headers))

    async def get_json(self, url: str, token: str) -> HttpResult:
        headers = {"Authorization": f"Bearer {token}"}
        async with self._session() as session:
            async with session.get(url, headers=headers) as resp:
                text = await resp.text()
                return HttpResult(resp.status, _json_or_none(text), headers=dict(resp.headers))

    async def post_sse(self, url: str, token: str, payload: Mapping[str, Any]) -> HttpResult:
        headers = {"Authorization": f"Bearer {token}", "Accept": "text/event-stream"}
        async with self._session() as session:
            async with session.post(url, json=dict(payload), headers=headers) as resp:
                text = await resp.text()
                result = HttpResult(resp.status, headers=dict(resp.headers))
                if result.ok:
                    result.events = parse_sse(text.splitlines())
                else:
                    result.body = _json_or_none(text)
                return result
