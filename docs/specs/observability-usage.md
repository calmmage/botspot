# Using botspot observability

The component defaults to enabled. It reuses the bot's Mongo database; without a
configured database or Bot, startup emits a warning and leaves persistence
unavailable. It never starts an unauthenticated dashboard. To use a dedicated
Mongo database instead, set `BOTSPOT_OBSERVABILITY_MONGO_URL` and
`BOTSPOT_OBSERVABILITY_MONGO_DATABASE` (default `botspot`). Install the existing
`extras` dependency group for PyMongo.

```python
from botspot import BotManager
from botspot.observability import record_usage

manager = BotManager(bot=bot, mongo_database={"enabled": True})
manager.setup_dispatcher(dispatcher)

# Inside your product handler; request/user/chat correlation is automatic.
await record_usage("transcription", minutes=2.4, cost=0.014, model="whisper-1",
                   file_kind="voice", outcome="ok")
```

The generic dashboard groups by day, user, kind, and model. Extend numeric
columns with `BOTSPOT_OBSERVABILITY_METRICS='["cost","minutes"]'`, and additional
category columns/groups with
`BOTSPOT_OBSERVABILITY_DIMENSIONS='["file_kind"]'`. Usage records are product
events, not inferred billing: bots supply cost and outcome themselves. Every
handled or ignored update is separately visible under Requests.

## Web server and owner access

Mount on an existing aiohttp application before it freezes:

```python
manager.deps.observability.mount(app)
# manager.setup_dispatcher(...) owns startup/shutdown; do not start a second runner.
```

Otherwise a small server starts at `127.0.0.1:8091`. Configure
`BOTSPOT_OBSERVABILITY_HOST` and `BOTSPOT_OBSERVABILITY_PORT` for the deployment.
Use a TLS reverse proxy; forward `/botspot/` unchanged. Disable proxy access
logging of authorization headers, cookies, and POST bodies. The built-in server
does not access-log requests. Route bodies contain telemetry; keep them private.

Set `BOTSPOT_ADMINS` (or the existing `BOTSPOT_ADMINS_STR`) to comma-separated
Telegram IDs or usernames. All configured admins can access the dashboard; the
first is the primary owner. Numeric IDs are preferable because usernames can
change. Session access is checked against the current allowlist on every request.
Set `BOTSPOT_OBSERVABILITY_PUBLIC_URL=https://your-bot.example` (an HTTPS origin,
no path) for owner-only private menu buttons and `/dashboard`, `/logs` commands.
Existing owner/private/default commands are retained. Username-only admins are
registered after a Telegram-verified private update or dashboard login supplies
the numeric ID. Telegram must already have a private chat with that owner;
registration failures warn and can retry on the next update/login.

Mini Apps POST signed `initData` to `/botspot/api/session`. Browser login uses
the HMAC Login Widget requested in the spec, which Telegram now documents as
[legacy Login Widget](https://core.telegram.org/widgets/login). Register the
site's domain with BotFather before browser login. No BotFather/domain changes
are automated by this library. Both paths verify Telegram signatures and reject
auth data older than 300 seconds (configurable `AUTH_MAX_AGE`). Signed HttpOnly
sessions expire after one day (`SESSION_TTL`); production cookies require HTTPS.
Mini App cookies use Secure + SameSite=None for Telegram's embedded web client;
browser/token cookies use Secure + SameSite=Lax.

Scripts can use `BOTSPOT_OBSERVABILITY_TOKEN`:

```sh
curl -H "Authorization: Bearer $BOTSPOT_OBSERVABILITY_TOKEN" \
  'https://your-bot.example/botspot/api/logs?level=ERROR&days=7'
```

The token also works in the sign-in form. Token sessions are invalidated when the
token changes. No credentials in query strings. Missing API auth and invalid or
non-admin credentials return 403. Public HTML shows sign-in, never telemetry.

Routes: `/botspot/dashboard`, `/botspot/logs`, `/botspot/bots`; JSON:
`/botspot/api/usage`, `/logs`, `/events`, `/errors`, `/bots`. Logs accept `level`,
`text` (literal substring), `user_id`, `request_id`, `from`, `to`, `days`, `page`.
Times are UTC. Today starts at UTC midnight. Tables fold after three rows, sort
on header click/keyboard, and error/log details open in a dialog with ×/Esc.

## Registry and retention

With a public URL, startup upserts the bot into `botspot_bot_registry` and refreshes
`last_heartbeat` every five minutes. Use
`BOTSPOT_OBSERVABILITY_REGISTRY_MONGO_URL` and
`BOTSPOT_OBSERVABILITY_REGISTRY_MONGO_DATABASE` to share that registry across bots;
otherwise it uses the bot's database. Registry pages show only entries whose owner
identity matches the signed user, or whose configured owners overlap this bot's
admins for the script-token fallback. Each linked bot authenticates independently.
The timestamp is observed history, not proof that a bot is still running.

Logs, events, errors, and product events use collections `botspot_logs`,
`botspot_events`, `botspot_errors`, `botspot_usage`. All records include the bot
identity and time, with request IDs when applicable. Log records expire after
`BOTSPOT_OBSERVABILITY_RETENTION_DAYS` (30 by default). Product events, request
events and errors remain persistent; apply any further retention in the host
deployment explicitly. Existing deployments
changing the TTL value may need Mongo `collMod` to update an existing index.
Indexed bot/time/request/user/level queries support bounded recent reads; full
usage totals aggregate the selected range. Real Mongo load latency must be
measured in the deployment; the local fake-Mongo browser journey is not that proof.

Writes have a three-second failure boundary and report redacted failure types to
stderr, without breaking product requests or error alerts. Registry/index/menu
failures also warn and continue. The heartbeat retries after five minutes;
menus retry on the next verified owner update/login. Application logs may contain
user message text; redaction removes credential keys, known configured secrets,
Telegram/API token patterns, URL credentials, query strings and fragments.
Avoid placing arbitrary unlabelled credentials into application log messages.

## Non-botspot / kurigram writer

```python
import asyncio
from loguru import logger
from botspot.observability.client import ObservabilityClient, record_event, record_usage

client = ObservabilityClient.from_url("mongodb://localhost:27017", "save_as_bot")
await client.ensure_indexes()
sink_id = logger.add(client.sink, level="INFO", loop=asyncio.get_running_loop())
await record_event(client, kind="download", outcome="ok", user_id=123, request_id="job-1")
await record_usage(client, "download", cost=0, request_id="job-1")
await logger.complete()
logger.remove(sink_id)
await client.close()
```

`log_sink(mongo_url, bot_name)` is a shortcut returning the same async sink; its
`__self__` exposes the client for indexing and closing. This writer uses no
aiogram dispatcher or Telegram calls. Mount `aiohttp_routes(client, OwnerAuth(...))`
when the non-botspot host needs its own dashboard. No consumer adoption or
production changes are included in this PR.
