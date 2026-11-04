"""Dashboard HTTP journeys with isolated in-memory Mongo, no external services."""

import datetime as dt
import re
from collections import defaultdict
from types import SimpleNamespace

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from botspot.components.new.observability.auth import OwnerAuth
from botspot.components.new.observability.dashboard import (
    aiohttp_routes,
    bots_report,
    logs_report,
    period_from_query,
    render_usage_html,
    usage_report,
)

UTC = dt.UTC


def matches(row, query):
    for field, expected in query.items():
        actual = row.get(field)
        if not isinstance(expected, dict) and actual != expected:
            return False
        for op, value in expected.items() if isinstance(expected, dict) else ():
            if op == "$gte" and not (actual is not None and actual >= value):
                return False
            if op == "$lt" and not (actual is not None and actual < value):
                return False
            if op == "$in" and not any(item in value for item in actual or []):
                return False
            if op == "$regex" and not re.search(value, str(actual), re.IGNORECASE):
                return False
    return True


class Cursor:
    def __init__(self, rows):
        self.rows = list(rows)

    def max_time_ms(self, value):
        return self

    def sort(self, field, order):
        self.rows.sort(
            key=lambda row: (row.get(field) is not None, row.get(field)), reverse=order < 0
        )
        return self

    def skip(self, count):
        self.rows = self.rows[count:]
        return self

    def limit(self, count):
        self.rows = self.rows[:count]
        return self

    async def to_list(self, length=None):
        return self.rows if length is None else self.rows[:length]


def expression(expr, row):
    if isinstance(expr, str) and expr.startswith("$"):
        return row.get(expr[1:])
    if not isinstance(expr, dict):
        return expr
    if "$ifNull" in expr:
        first, fallback = expr["$ifNull"]
        value = expression(first, row)
        return value if value is not None else expression(fallback, row)
    if "$dateToString" in expr:
        return expression(expr["$dateToString"]["date"], row).strftime("%Y-%m-%d")
    if "$convert" in expr:
        try:
            return float(expression(expr["$convert"]["input"], row))
        except (TypeError, ValueError):
            return 0
    if "$in" in expr:
        first, values = expr["$in"]
        return expression(first, row) in values
    if "$cond" in expr:
        check, yes, no = expr["$cond"]
        return expression(yes if expression(check, row) else no, row)
    raise AssertionError(expr)


class Collection:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.queries = []
        self.pipeline = None

    def find(self, query):
        self.queries.append(query)
        return Cursor(row for row in self.rows if matches(row, query))

    async def count_documents(self, query, **kwargs):
        self.queries.append(query)
        return sum(matches(row, query) for row in self.rows)

    async def aggregate(self, pipeline, **kwargs):
        self.pipeline = pipeline
        rows = [row for row in self.rows if matches(row, pipeline[0]["$match"])]
        result = {}
        for name, stages in pipeline[1]["$facet"].items():
            group = stages[0]["$group"]
            groups = {}
            for row in rows:
                key = expression(group["_id"], row)
                bucket = groups.setdefault(key, {"_id": key})
                for field, value in group.items():
                    if field != "_id":
                        bucket[field] = bucket.get(field, 0) + expression(value["$sum"], row)
            values = list(groups.values())
            for stage in stages[1:]:
                if "$sort" in stage:
                    for field, order in reversed(list(stage["$sort"].items())):
                        values.sort(
                            key=lambda row: str(row[field]) if field == "_id" else row[field],
                            reverse=order < 0,
                        )
                elif "$limit" in stage:
                    values = values[: stage["$limit"]]
            result[name] = values
        return Cursor([result])


class Database(defaultdict):
    def __init__(self):
        super().__init__(Collection)


def fake_client():
    now = dt.datetime.now(UTC)
    client = SimpleNamespace(
        database=Database(),
        registry_database=Database(),
        bot_name="example_bot",
        metrics=("cost", "minutes"),
    )
    client.database["botspot_usage"].rows = [
        {
            "bot": "example_bot",
            "time": now - dt.timedelta(minutes=i),
            "kind": "transcription",
            "user_id": 1,
            "model": "whisper-1",
            "minutes": 2,
            "cost": 0.1,
            "outcome": "ok",
            "request_id": f"req-{i}",
        }
        for i in range(250)
    ] + [{"bot": "other_bot", "time": now, "cost": 9999, "outcome": "ok"}]
    client.database["botspot_events"].rows = [
        {
            "bot": "example_bot",
            "started_at": now,
            "request_id": "req-0",
            "user_id": 1,
            "outcome": "ok",
        }
    ]
    client.database["botspot_errors"].rows = [
        {
            "bot": "example_bot",
            "time": now,
            "error_type": "RecordingError",
            "error_message": "Download failed",
            "traceback": "trace </script><script>alert(1)</script>",
            "request_id": "req-0",
        }
    ]
    client.database["botspot_logs"].rows = [
        {
            "bot": "example_bot",
            "time": now,
            "message": "Download [failed]",
            "level": "ERROR",
            "request_id": "req-0",
            "user_id": 1,
        }
    ]
    return client


def test_today_is_calendar_utc_and_bad_ranges_rejected():
    now = dt.datetime(2026, 11, 4, 13, 30, tzinfo=UTC)
    since, until, days = period_from_query({"days": "1"}, now)
    assert since == dt.datetime(2026, 11, 4, tzinfo=UTC)
    assert until == now and days == 1
    for query in ({"days": "bad"}, {"from": "2026-11-05", "to": "2026-11-01"}, {"from": "bad"}):
        with pytest.raises(web.HTTPBadRequest):
            period_from_query(query, now)


@pytest.mark.asyncio
async def test_complete_aggregate_totals_do_not_equal_limited_rows_and_other_bots_hidden():
    client = fake_client()
    report = await usage_report(client, {})
    assert report["total"]["requests"] == 250
    assert report["total"]["minutes"] == 500
    assert report["total"]["cost"] == pytest.approx(25)
    assert len(report["recent"]) == 200
    assert report["truncated"]["recent"]
    assert report["kind"][0]["key"] == "transcription"
    assert report["total"]["ok"] == 250
    assert report["events"][0]["request_id"] == "req-0"
    assert report["error_count"] == 1
    client.dimensions = ("file_kind",)
    for row in client.database["botspot_usage"].rows:
        row["file_kind"] = "voice"
    extended = await usage_report(client, {})
    assert extended["file_kind"][0]["key"] == "voice"
    assert extended["file_kind"][0]["requests"] == 250
    assert "By file kind" in render_usage_html(extended)
    assert client.database["botspot_usage"].pipeline[0]["$match"]["bot"] == "example_bot"


@pytest.mark.asyncio
async def test_log_filters_literal_text_time_user_request_level_and_page():
    client = fake_client()
    report = await logs_report(
        client, {"text": "[failed]", "level": "error", "user": "1", "request_id": "req-0"}
    )
    assert len(report["rows"]) == 1
    query = client.database["botspot_logs"].queries[-1]
    assert query["message"]["$regex"] == r"\[failed\]"
    assert query["user_id"] == 1 and query["level"] == "ERROR"
    assert not (await logs_report(client, {"page": "1"}))["rows"]
    for query in ({"level": "$gt"}, {"page": "nonsense"}, {"text": "x" * 201}):
        with pytest.raises(web.HTTPBadRequest):
            await logs_report(client, query)


@pytest.mark.asyncio
async def test_registry_visible_only_to_matching_owner_including_token_admins():
    client = fake_client()
    registry = client.registry_database["botspot_bot_registry"]
    registry.rows = [
        {"username": "mine", "owners": ["id:1"], "last_heartbeat": 3},
        {"username": "also_mine", "owners": ["username:petr"], "last_heartbeat": 2},
        {"username": "other", "owners": ["id:2"], "last_heartbeat": 1},
    ]
    assert [row["username"] for row in (await bots_report(client, {"id": 1}))["rows"]] == ["mine"]
    token_rows = (await bots_report(client, {"token_auth": True}, ["1", "@Petr"]))["rows"]
    assert [row["username"] for row in token_rows] == ["mine", "also_mine"]


@pytest.mark.asyncio
async def test_render_escapes_errors_and_preserves_request_logs_return():
    report = await usage_report(fake_client(), {})
    rendered = render_usage_html(report, "example_bot")
    assert "</script><script>alert(1)" not in rendered
    assert r"\u003c/script\u003e" in rendered
    assert 'href="#errors"' in rendered
    assert "/botspot/logs?request_id=req-0" in rendered
    assert 'aria-label="Close">×' in rendered


@pytest.mark.asyncio
async def test_http_entry_auth_result_and_json_share_owner_guard():
    client = fake_client()
    auth = OwnerAuth("12345:dummy", ["1"], token="test-token")
    auth.secure_cookies = False
    app = web.Application()
    app.add_routes(aiohttp_routes(client, auth))
    async with TestClient(TestServer(app)) as browser:
        assert (await browser.get("/botspot/api/usage")).status == 403
        assert (
            await browser.get("/botspot/dashboard", headers={"Authorization": "Bearer wrong"})
        ).status == 403
        response = await browser.get("/botspot/dashboard")
        assert "Sign in as a bot owner" in await response.text()
        assert (await browser.post("/botspot/api/session", json={"token": "wrong"})).status == 403
        assert (
            await browser.post("/botspot/api/session", json={"token": "test-token"})
        ).status == 200
        for path in (
            "dashboard",
            "logs",
            "bots",
            "api/usage",
            "api/logs",
            "api/events",
            "api/errors",
            "api/bots",
        ):
            response = await browser.get("/botspot/" + path)
            assert response.status == 200, (path, await response.text())
            assert response.headers["Cache-Control"] == "no-store"
        usage = await (await browser.get("/botspot/api/usage")).json()
        assert usage["total"]["requests"] == 250
        logs = await (await browser.get("/botspot/api/logs?request_id=req-0")).json()
        assert logs["rows"][0]["request_id"] == "req-0"
        assert (await browser.get("/botspot/api/logs?from=bad")).status == 400
