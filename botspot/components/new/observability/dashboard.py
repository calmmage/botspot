"""Owner dashboard, ported from Whisper's usage dashboard (origin/dev 13d07e7).

The compact tables, folding, range navigation and traceback dialog retain the
Whisper layout. Reads are bot scoped; totals aggregate the complete selected
range in Mongo rather than treating a limited request list as the total.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import html
import inspect
import json
import re
from typing import Any
from urllib.parse import urlencode, urlsplit

from aiohttp import web

UTC = dt.UTC
PAGE_SIZE = 200
GROUP_LIMIT = 200


def period_from_query(query: Any, now: dt.datetime | None = None) -> tuple:
    """Return a UTC range, including calendar Today rather than a rolling day."""
    now = now or dt.datetime.now(UTC)
    try:
        days = min(365, max(1, int(query.get("days", "7"))))
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if days > 1:
            start -= dt.timedelta(days=days - 1)
        if query.get("from"):
            start = _date(query["from"])
        until = _date(query["to"]) if query.get("to") else now
        if query.get("to") and len(query["to"]) == 10:
            until += dt.timedelta(days=1)
        if start >= until:
            raise ValueError("Start must precede end")
    except (ValueError, TypeError) as error:
        raise web.HTTPBadRequest(text="Invalid time range") from error
    return start, until, days


def _date(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value)
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _public(value: Any) -> Any:
    if isinstance(value, dt.datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, dict):
        return {key: _public(item) for key, item in value.items() if key != "_id"}
    if isinstance(value, (tuple, list)):
        return [_public(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _metrics(client: Any) -> tuple[str, ...]:
    # Field paths must be literal top-level fields, never Mongo operators.
    return tuple(
        field
        for field in getattr(client, "metrics", ("cost",))
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", field)
        and field not in {"requests", "ok", "error", "ignored", "key", "_id"}
    )


def _dimensions(client: Any) -> tuple[str, ...]:
    return tuple(
        field
        for field in getattr(client, "dimensions", ())
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", field)
        and field
        not in {
            "day",
            "user",
            "kind",
            "model",
            "total",
            "metrics",
            "dimensions",
            "recent",
            "events",
            "errors",
            "period",
            "limits",
            "truncated",
            "error_count",
        }
    )


async def _aggregate(collection: Any, pipeline: list) -> list:
    cursor = collection.aggregate(pipeline, maxTimeMS=3000, allowDiskUse=True)
    if inspect.isawaitable(cursor):
        cursor = await cursor
    return await cursor.to_list(length=1)


async def _rows(collection: Any, match: dict, field: str, page: int = 0) -> list:
    return (
        await collection.find(match)
        .max_time_ms(3000)
        .sort(field, -1)
        .skip(page * PAGE_SIZE)
        .limit(PAGE_SIZE + 1)
        .to_list(length=PAGE_SIZE + 1)
    )


def _scope(client: Any, query: Any, field: str = "time") -> tuple[dict, dict]:
    since, until, days = period_from_query(query)
    return (
        {"bot": client.bot_name, field: {"$gte": since, "$lt": until}},
        {"since": _public(since), "until": _public(until), "days": days},
    )


async def usage_report(client: Any, query: Any) -> dict:
    """Aggregate all product records and fetch bounded recent updates/errors."""
    match, period = _scope(client, query)
    metrics = _metrics(client)
    dimensions = _dimensions(client)
    groups_names = ("day", "user", "kind", "model", *dimensions)
    sums = {
        field: {
            "$sum": {
                "$convert": {
                    "input": "$" + field,
                    "to": "double",
                    "onError": 0,
                    "onNull": 0,
                }
            }
        }
        for field in metrics
    }
    sums.update(
        {
            "requests": {"$sum": 1},
            "ok": {"$sum": {"$cond": [{"$in": ["$outcome", ["ok", "success"]]}, 1, 0]}},
            "error": {"$sum": {"$cond": [{"$in": ["$outcome", ["error", "fail"]]}, 1, 0]}},
        }
    )
    facet: dict[str, list] = {"total": [{"$group": {"_id": None, **sums}}]}
    for name in groups_names:
        key = {"$dateToString": {"format": "%Y-%m-%d", "date": "$time", "timezone": "UTC"}}
        if name != "day":
            field = "user_id" if name == "user" else name
            key = {"$ifNull": ["$" + field, "$user" if name == "user" else "—"]}
        facet[name] = [
            {"$group": {"_id": key, **sums}},
            {"$sort": {"_id": -1} if name == "day" else {"requests": -1, "_id": 1}},
            {"$limit": GROUP_LIMIT + 1},
        ]
    db = client.database
    event_match, _ = _scope(client, query, "started_at")
    grouped, recent, events, errors, error_count = await asyncio.gather(
        _aggregate(db["botspot_usage"], [{"$match": match}, {"$facet": facet}]),
        _rows(db["botspot_usage"], match, "time"),
        _rows(db["botspot_events"], event_match, "started_at"),
        _rows(db["botspot_errors"], match, "time"),
        db["botspot_errors"].count_documents(match, maxTimeMS=3000),
    )
    result = grouped[0] if grouped else {}
    total = {"requests": 0, "ok": 0, "error": 0, **dict.fromkeys(metrics, 0)}
    total.update(_public(next(iter(result.get("total", [])), {})))
    report = {
        "period": period,
        "metrics": metrics,
        "dimensions": dimensions,
        "total": total,
        "recent": _public(recent[:PAGE_SIZE]),
        "events": _public(events[:PAGE_SIZE]),
        "errors": _public(errors[:PAGE_SIZE]),
        "error_count": error_count,
        "limits": {"rows": PAGE_SIZE, "groups": GROUP_LIMIT},
        "truncated": {
            "recent": len(recent) > PAGE_SIZE,
            "events": len(events) > PAGE_SIZE,
            "errors": error_count > PAGE_SIZE,
        },
    }
    for name in groups_names:
        groups = result.get(name, [])
        report[name] = [
            {"key": item.get("_id") or "—", **_public(item)} for item in groups[:GROUP_LIMIT]
        ]
        report["truncated"][name] = len(groups) > GROUP_LIMIT
    return report


def _page_number(query: Any) -> int:
    try:
        return min(10000, max(0, int(query.get("page", "0"))))
    except (TypeError, ValueError) as error:
        raise web.HTTPBadRequest(text="Invalid page") from error


async def logs_report(client: Any, query: Any, collection: str = "botspot_logs") -> dict:
    field = "started_at" if collection == "botspot_events" else "time"
    match, period = _scope(client, query, field)
    if query.get("level"):
        level = query["level"].upper()
        if level not in {"TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"}:
            raise web.HTTPBadRequest(text="Invalid level")
        match["level"] = level
    for field_name in ("request_id", "user_id"):
        value = query.get(field_name) or (query.get("user") if field_name == "user_id" else None)
        if value:
            if len(value) > 200:
                raise web.HTTPBadRequest(text="Filter too long")
            match[field_name] = (
                int(value) if field_name == "user_id" and value.isdecimal() else value
            )
    if query.get("text"):
        if len(query["text"]) > 200:
            raise web.HTTPBadRequest(text="Filter too long")
        match["message"] = {"$regex": re.escape(query["text"]), "$options": "i"}
    page = _page_number(query)
    rows = await _rows(client.database[collection], match, field, page)
    return {
        "period": period,
        "rows": _public(rows[:PAGE_SIZE]),
        "page": page,
        "has_more": len(rows) > PAGE_SIZE,
        "page_size": PAGE_SIZE,
    }


async def bots_report(client: Any, user: dict, admins=()) -> dict:
    """Only list registry entries sharing this authenticated owner identity."""
    owners = []
    if user.get("id"):
        owners.append("id:" + str(user["id"]))
    if user.get("username"):
        owners.append("username:" + user["username"].lstrip("@").lower())
    if user.get("token_auth"):
        owners = [
            ("id:" if str(admin).isdigit() else "username:") + str(admin).lstrip("@").lower()
            for admin in admins
        ]
    match = {"owners": {"$in": owners}}
    rows = (
        await client.registry_database["botspot_bot_registry"]
        .find(match)
        .max_time_ms(3000)
        .sort("last_heartbeat", -1)
        .limit(PAGE_SIZE + 1)
        .to_list(length=PAGE_SIZE + 1)
    )
    return {"rows": _public(rows[:PAGE_SIZE]), "has_more": len(rows) > PAGE_SIZE}


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _number(value: Any) -> str:
    return f"{value:,.3f}".rstrip("0").rstrip(".") if isinstance(value, float) else _e(value)


def _time(value: Any) -> str:
    stamp = _e(value)
    label = _e(str(value or "")[5:16].replace("T", " "))
    return f'<time datetime="{stamp}" data-v="{stamp}" title="{stamp}">{label}</time>'


def _request_link(row: dict) -> str:
    request_id = row.get("request_id")
    if not request_id:
        return "—"
    return f'<a href="/botspot/logs?{_e(urlencode({"request_id": request_id, "days": 365}))}" title="{_e(request_id)}" data-v="{_e(request_id)}" aria-label="Logs for {_e(request_id)}">Logs</a>'


def _table(title: str, columns: list, rows: list, *, section_id: str = "") -> str:
    heads = "".join(
        f'<th scope="col" tabindex="0" role="button" class="{cls}" aria-sort="none">{_e(label)}</th>'
        for _, label, cls in columns
    )
    body = "".join(
        "<tr>"
        + "".join(f'<td class="{cls}">{render(row)}</td>' for render, _, cls in columns)
        + "</tr>"
        for row in rows
    )
    return (
        f'<section id="{_e(section_id)}"><h2>{_e(title)}</h2><div class="wrap">'
        f'<table class="sortable fold"><thead><tr>{heads}</tr></thead><tbody>'
        f"{body or f'<tr><td colspan={len(columns)} class=empty>Nothing yet</td></tr>'}"
        "</tbody></table></div></section>"
    )


def _metric_columns(metrics: tuple) -> list:
    return [
        (lambda row, field=field: _number(row.get(field, 0)), field.replace("_", " ").title(), "n")
        for field in metrics
    ]


def render_usage_html(report: dict, bot_name: str = "") -> str:
    """Whisper's quiet usage layout, with generic product metric extensions."""
    metrics, total = report["metrics"], report["total"]
    ranges = " ".join(
        f'<a href="?days={days}"'
        f"{' aria-current=page' if days == report['period']['days'] else ''}>{label}</a>"
        for days, label in ((1, "Today"), (7, "7 days"), (30, "30 days"), (90, "90 days"))
    )
    summary = f"<b>{total['requests']}</b> product events · <b>{total['ok']}</b> ok · <b>{total['error']}</b> failed"
    summary += "".join(f" · <b>{_number(total.get(field, 0))}</b> {_e(field)}" for field in metrics)
    summary += f' · <a href="#errors"><b>{report["error_count"]}</b> errors</a>'
    body = (
        f'<nav class="ranges" aria-label="Date range">{ranges}</nav><p class="totals">{summary}</p>'
    )
    for group in ("day", "kind", "model", "user", *report.get("dimensions", ())):
        columns = [
            (lambda row: _e(row.get("key")), group.title(), "k"),
            (lambda row: _number(row.get("requests", 0)), "Req", "n"),
            (lambda row: f"{row.get('ok', 0)} · {row.get('error', 0)}", "OK · Fail", "n"),
        ]
        body += _table(
            "By " + group.replace("_", " "), columns + _metric_columns(metrics), report[group]
        )
        if report["truncated"].get(group):
            body += f'<p class="muted">Top {GROUP_LIMIT} groups; totals include all events.</p>'
    body += _table(
        "Product events",
        [
            (lambda row: _time(row.get("time")), "When (UTC)", "t"),
            (lambda row: _e(row.get("user_id") or row.get("user")), "User", "k"),
            (lambda row: _e(row.get("kind")), "Kind", "k wide"),
            (lambda row: _e(row.get("outcome")), "Outcome", "k"),
            *[
                (
                    lambda row, field=field: _e(row.get(field)),
                    field.replace("_", " ").title(),
                    "k wide",
                )
                for field in report.get("dimensions", ())
            ],
            *_metric_columns(metrics),
            (_request_link, "Request", "k"),
        ],
        report["recent"],
    )
    body += _table(
        "Requests",
        [
            (lambda row: _time(row.get("started_at")), "When (UTC)", "t"),
            (lambda row: _e(row.get("user_id")), "User", "k"),
            (
                lambda row: (
                    f'<span title="{_e(row.get("handler"))}">{_e(row.get("update_kind") or row.get("kind"))}</span>'
                ),
                "Update",
                "k wide",
            ),
            (lambda row: _e(row.get("outcome")), "Outcome", "k"),
            (lambda row: _number(row.get("latency_ms", 0)), "ms", "n wide"),
            (_request_link, "Request", "k"),
        ],
        report["events"],
    )
    errors = [{**row, "index": index} for index, row in enumerate(report["errors"])]
    body += _table(
        "Errors",
        [
            (lambda row: _time(row.get("time")), "When (UTC)", "t"),
            (lambda row: _e(row.get("user_id")), "User", "k"),
            (
                lambda row: (
                    f'<button class="trace" data-trace="{row["index"]}" title="{_e(row.get("error_message"))}">{_e(row.get("error_type") or "Traceback")}</button>'
                ),
                "Error",
                "k",
            ),
            (_request_link, "Request", "k"),
        ],
        errors,
        section_id="errors",
    )
    if any(report["truncated"].get(name) for name in ("recent", "events", "errors")):
        body += f'<p class="muted">Recent tables show up to {PAGE_SIZE} rows. Totals cover the full range; use Logs for older requests.</p>'
    traces = [
        f"{row.get('error_type', '')}: {row.get('error_message', '')}\n\n{row.get('traceback', '')}"
        for row in errors
    ]
    return _page("Usage", body, bot_name, traces)


def render_logs_html(report: dict, query: Any, bot_name: str = "") -> str:
    def input_field(name: str, placeholder: str, kind: str = "text") -> str:
        return f'<input type="{kind}" name="{name}" value="{_e(query.get(name, ""))}" placeholder="{placeholder}" aria-label="{placeholder}">'

    options = '<option value="">All levels</option>' + "".join(
        f"<option{' selected' if query.get('level', '').upper() == level else ''}>{level}</option>"
        for level in ("INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL")
    )
    body = (
        '<form class="filters" method="get"><select name="level" aria-label="Level">'
        + options
        + "</select>"
    )
    body += f'<input type="hidden" name="days" value="{_e(query.get("days", "7"))}">'
    body += (
        input_field("text", "Text")
        + input_field("user_id", "User ID")
        + input_field("request_id", "Request ID")
    )
    body += input_field("from", "From (UTC)", "datetime-local") + input_field(
        "to", "To (UTC)", "datetime-local"
    )
    body += '<button>Filter</button><a href="/botspot/logs">Clear</a></form>'
    body += _table(
        "Logs",
        [
            (lambda row: _time(row.get("time")), "When (UTC)", "t"),
            (lambda row: _e(row.get("level")), "Level", "k"),
            (lambda row: _e(row.get("user_id")), "User", "k wide"),
            (lambda row: _e(row.get("logger")), "Logger", "k wide"),
            (
                lambda row: (
                    f'<button class="trace message" data-trace="{row["index"]}" title="{_e(row.get("message"))}">{_e(row.get("message"))}</button>'
                ),
                "Message",
                "message-cell",
            ),
            (_request_link, "Request", "k wide"),
        ],
        [{**row, "index": index} for index, row in enumerate(report["rows"])],
    )
    body += '<nav class="pagination">'
    for page, label in ((report["page"] - 1, "← Newer"), (report["page"] + 1, "Older →")):
        if page >= 0 and (label == "← Newer" or report["has_more"]):
            body += f'<a href="?{_e(urlencode({**dict(query), "page": page}))}">{label}</a>'
    body += "</nav>"
    traces = [f"{row.get('message', '')}\n\n{row.get('exception', '')}" for row in report["rows"]]
    return _page("Logs", body, bot_name, traces)


def render_bots_html(report: dict, bot_name: str = "") -> str:
    def link(row: dict) -> str:
        url = row.get("dashboard_url", "")
        label = _e(row.get("username") or row.get("bot"))
        return f'<a href="{_e(url)}">{label}</a>' if urlsplit(url).scheme == "https" else label

    body = _table(
        "Registered bots",
        [
            (link, "Bot", "k"),
            (lambda row: _e(row.get("version")), "Version", "k wide"),
            (lambda row: _e(row.get("host")), "Host", "k wide"),
            (lambda row: _e(row.get("last_heartbeat")), "Last heartbeat (UTC)", "t"),
        ],
        report["rows"],
    )
    if report["has_more"]:
        body += f'<p class="muted">Showing the {PAGE_SIZE} most recent bots.</p>'
    return _page("Bots", body, bot_name)


_STYLE = """
:root { --bg:#f7f8fa; --panel:#fff; --text:#18212f; --muted:#667085; --line:#e3e7ee; }
@media (prefers-color-scheme:dark) { :root { --bg:#111418; --panel:#181c22; --text:#e6e9ef; --muted:#8b95a5; --line:#262c35; } }
* { box-sizing:border-box; } body { margin:0; background:var(--bg); color:var(--text); font:14px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
main { max-width:1080px; margin:0 auto; padding:20px 16px 40px; } header { display:flex; flex-wrap:wrap; gap:8px 16px; align-items:baseline; }
h1 { font-size:20px; margin:0; } nav a,a { color:inherit; } nav a { color:var(--muted); text-decoration:none; margin-right:10px; }
nav a[aria-current] { color:var(--text); font-weight:600; } .ranges { margin:12px 0; } .totals,.muted { color:var(--muted); } .totals b { color:var(--text); font-weight:600; }
h2 { font-size:13px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); margin:22px 0 6px; } .wrap { overflow-x:auto; max-width:100%; }
table { width:100%; border-collapse:collapse; background:var(--panel); border:1px solid var(--line); border-radius:6px; }
th,td { padding:6px 10px; border-bottom:1px solid var(--line); text-align:left; white-space:nowrap; }
th { font-size:12px; font-weight:600; color:var(--muted); cursor:pointer; user-select:none; } th[aria-sort=descending]::after { content:" ↓"; } th[aria-sort=ascending]::after { content:" ↑"; }
.n { text-align:right; font-variant-numeric:tabular-nums; } .t { font-variant-numeric:tabular-nums; color:var(--muted); }
td.k { max-width:220px; overflow:hidden; text-overflow:ellipsis; } tr:last-child td { border-bottom:0; } tr.more td { color:var(--muted); text-align:center; } tr.hidden { display:none; }
td.empty { color:var(--muted); text-align:center; } button,input,select { font:inherit; color:inherit; background:var(--panel); border:1px solid var(--line); border-radius:4px; padding:5px 8px; }
button { cursor:pointer; } button.trace { border:0; padding:0; color:inherit; text-decoration:underline; text-underline-offset:3px; } .message-cell { max-width:400px; } button.message { display:block; text-align:left; max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.filters { display:flex; flex-wrap:wrap; gap:8px; margin-top:16px; } .filters input { min-width:0; width:160px; } .filters input[name=request_id] { width:210px; } .filters a { padding:5px; } .pagination { margin:16px 0; }
dialog { width:min(900px,92vw); max-width:92vw; border:1px solid var(--line); border-radius:8px; background:var(--panel); color:var(--text); padding:0; }
dialog form { position:sticky; top:0; display:flex; justify-content:flex-end; background:var(--panel); } dialog button { border:0; background:none; color:var(--muted); font-size:22px; line-height:1; padding:6px 12px; }
dialog pre { margin:0; padding:14px; max-height:70vh; overflow:auto; font-size:12px; white-space:pre-wrap; overflow-wrap:anywhere; } dialog::backdrop { background:rgba(0,0,0,.35); }
@media (max-width:600px) { .wide { display:none; } body { font-size:13px; } th,td { padding:6px 5px; } td.k { max-width:84px; } main { padding:16px 12px 32px; } .message-cell { max-width:200px; } .filters input,.filters input[name=request_id] { flex:1 1 140px; width:140px; } }
"""

_SCRIPT = """
function fold(table) {
 const body=table.tBodies[0]; body.querySelectorAll('tr.more').forEach(r=>r.remove()); const rows=[...body.rows];
 rows.forEach((r,i)=>r.classList.toggle('hidden',i>=3&&!table.dataset.open));
 if(rows.length>3&&!table.dataset.open) { const more=body.insertRow();more.className='more';const cell=more.insertCell();cell.colSpan=table.tHead.rows[0].cells.length;
 const button=document.createElement('button');button.textContent='… '+(rows.length-3)+' more';cell.appendChild(button);button.onclick=()=>{table.dataset.open='1';fold(table);}; }
}
document.querySelectorAll('table.sortable').forEach(table=>{
 [...table.tHead.rows[0].cells].forEach((th,col)=>{
 const sort=()=>{const asc=th.getAttribute('aria-sort')==='descending';table.querySelectorAll('th').forEach(h=>h.setAttribute('aria-sort','none'));th.setAttribute('aria-sort',asc?'ascending':'descending');
 const body=table.tBodies[0];const rows=[...body.rows].filter(r=>!r.classList.contains('more')&&!r.querySelector('.empty'));
 const val=r=>{const v=r.cells[col].querySelector('[data-v]')?.dataset.v??r.cells[col].dataset.v??r.cells[col].textContent;const n=v.replaceAll(',','');return isNaN(+n)||n===''?v:+n;};
 rows.sort((a,b)=>(val(a)>val(b)?1:val(a)<val(b)?-1:0)*(asc?1:-1));rows.forEach(r=>body.appendChild(r));fold(table);};
 th.onclick=sort;th.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();sort();}};
 });fold(table);
});
const dialog=document.getElementById('tb');document.querySelectorAll('[data-trace]').forEach(button=>button.onclick=()=>{dialog.querySelector('pre').textContent=TRACEBACKS[+button.dataset.trace];dialog.showModal();});
dialog.onclick=e=>{if(e.target===dialog)dialog.close();};
"""


def _page(title: str, body: str, bot_name: str = "", traces: list | None = None) -> str:
    trace_json = (
        json.dumps(traces or [])
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    nav = "".join(
        f'<a href="/botspot/{path}"{" aria-current=page" if title == label else ""}>{label}</a>'
        for path, label in (("dashboard", "Usage"), ("logs", "Logs"), ("bots", "Bots"))
    )
    return (
        f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{_e(bot_name)} · {_e(title)}</title><style>{_STYLE}</style></head><body><main>"
        f'<header><h1>{_e(title)}</h1><nav aria-label="Dashboard">{nav}</nav>'
        f'<span class="muted">{_e(bot_name)}</span></header>{body}</main>'
        '<dialog id="tb" aria-label="Details"><form method="dialog"><button aria-label="Close">×</button></form><pre></pre></dialog>'
        f"<script>const TRACEBACKS={trace_json};{_SCRIPT}</script></body></html>"
    )


def aiohttp_routes(client: Any, auth: Any, bot_username: str = "") -> list:
    """Routes the host mounts before its aiohttp application starts."""
    from .auth import sign_in_html

    async def protected(request: web.Request, resource: str) -> web.Response:
        authenticated = await auth.authenticate(request)
        is_json = request.path.startswith("/botspot/api/")
        if not authenticated:
            if is_json:
                raise web.HTTPForbidden(text="Owner authentication required")
            return web.Response(
                text=sign_in_html(bot_username or client.bot_name),
                content_type="text/html",
                headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
            )
        if resource == "usage":
            report = await usage_report(client, request.query)
            rendered = None if is_json else render_usage_html(report, client.bot_name)
        elif resource == "bots":
            report = await bots_report(client, request.get("botspot_user", {}), auth.admins)
            rendered = None if is_json else render_bots_html(report, client.bot_name)
        else:
            report = await logs_report(client, request.query, "botspot_" + resource)
            rendered = None if is_json else render_logs_html(report, request.query, client.bot_name)
        headers = {
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        }
        if is_json:
            return web.json_response(report, headers=headers)
        return web.Response(text=rendered, content_type="text/html", headers=headers)

    async def session(request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except (ValueError, TypeError) as error:
            raise web.HTTPBadRequest(text="Expected JSON") from error
        if not isinstance(data, dict):
            raise web.HTTPBadRequest(text="Expected JSON object")
        return await auth.session_response(data, request)

    def handler(resource: str):
        async def get(request: web.Request) -> web.Response:
            return await protected(request, resource)

        return get

    routes = [web.post("/botspot/api/session", session)]
    for path, resource in (("dashboard", "usage"), ("logs", "logs"), ("bots", "bots")):
        routes.append(web.get("/botspot/" + path, handler(resource)))
    for resource in ("usage", "logs", "events", "errors", "bots"):
        routes.append(web.get("/botspot/api/" + resource, handler(resource)))
    return routes
