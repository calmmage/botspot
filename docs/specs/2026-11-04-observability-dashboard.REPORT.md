# Botspot observability implementation report

Built on `feat/observability-owner-dashboard`; [desktop and 390 px walkthrough](../journey/observability/index.html), [configuration and standalone writer](observability-usage.md). The required `uv run pytest -q` passes: **335 passed in 5.75s**.

Scope: botspot library only. No consumer adoption, deployment, real Telegram sends,
server SSH, merges, `main`/`dev` pushes, key reads, or `~/calm/notes` edits.

- Base: freshly fetched `origin/dev`, `9128c7cff96b0c0193834f85a4b0b0853bfcc9f0`.
- Spec: copied unchanged into this branch as `2026-11-04-observability-dashboard.md`.
- Source port: read Whisper `src/usage_log.py`, `src/usage_dashboard.py`, and its journey
  from local `origin/dev`. That ref is now `13d07e73b06e9fc69de7734d8f1cda0062b0c0fc`,
  newer than the spec's `8389c76`. The compact layout, folding, date ranges, newest-first
  days, sortable tables, error-count anchor, and ×/Esc dialog carry across.
- Parallel harness work: auth/registration, dashboard/read side, middleware/error
  archive. Root inspected all returns and code, integrated the client/lifecycle,
  and ran the final tests and browser journey. Independent review found registration
  and heartbeat failure paths; the final code and outage tests cover them.

Petr's requested botspot work:

- [x] **Persistent logs.** INFO+ Loguru sink writes redacted time, level, logger,
  message, bot, request/user/chat IDs and exception text to `botspot_logs`. Thirty-day
  TTL plus bot/time/request/user/level indexes. Secret fields, configured secrets,
  Telegram/API-token patterns, URI credentials and URL query/fragment data are
  removed before writes. Log retention is configurable; product events, requests
  and errors remain persistent for longer-range analytics.
- [x] **Request events.** One row per update in `botspot_events`, including kind,
  actual selected handler, user/chat/update IDs, start/finish, latency, outcome and
  error type. Request context correlates concurrent updates' logs and product events.
  Real aiogram routing tests cover ok/error/ignored and callback updates.
- [x] **Errors.** Middleware archives failures even without the alert component.
  Existing `error_handler` also upserts `botspot_errors` by bot/request ID and binds
  its error log to that request. Existing user/developer reporting still runs;
  all test sends use mocks. A unique bot/request index prevents duplicate error cards.
- [x] **Product metrics API.** `await botspot.observability.record_usage(kind, **fields)`;
  generic day/user/kind/model grouping, configurable numeric metrics and category
  dimensions. Whisper-style minutes/cost/model/file-kind demonstrated without
  hard-coding transcription columns. Cost is supplied by the product, not inferred
  or joined to a Whisper-specific collection.
- [x] **Dashboard.** HTML usage/logs/bots pages and JSON twins under `/botspot/`.
  Full-range Mongo aggregation for totals; bounded recent rows/groups explicitly
  disclose limits. Logs filter by level, literal text, user, request and UTC time,
  with pagination and sorting. Request/error rows open matching logs across the
  retention window. Mount on the host's aiohttp app before freeze, or start the
  built-in server (loopback `8091` by default; host/port configurable).
- [x] **Owner auth through Telegram.** Mini App initData and Login Widget HMAC
  verification, freshness/future rejection, ID/username allowlist, signed expiring
  HttpOnly cookies, current-admin recheck, and 403 for invalid/non-owner access.
  Secure/SameSite=None for Mini App iframe sessions; Secure/Lax for browser/token
  sessions. Script Bearer/X-Botspot-Token fallback plus token sign-in; rotating the
  fallback token invalidates its sessions. No credential-bearing query strings.
- [x] **Auto-registration in the bot account.** HTTPS public origin enables
  private owner menu buttons and chat-scoped `/dashboard`/`/logs`, preserving
  inherited commands. Registry upsert includes bot ID, username, URL, version,
  host, normalized owner identities and five-minute heartbeat. Separate registry
  Mongo configuration supported. Registry visibility follows the verified owner,
  or configured owners for token auth. Without a URL, telemetry remains active
  and startup explains why buttons are absent.
- [x] **Standalone writer for non-botspot bots.** `botspot.observability.client`
  exposes `log_sink(mongo_url, bot_name)`, `ObservabilityClient`, `record_event` and
  `record_usage`. No dispatcher or Telegram calls needed. Standalone events get
  default timestamps/outcome and appear in the same dashboard; the host can mount
  the same routes. It owns explicit indexing/draining/closing rather than creating
  a separate service.

Choices made without questions:

- Observability defaults enabled and reuses the existing bot Mongo database.
  Without Mongo or Bot configuration, it warns and remains unavailable; it does
  not silently invent a localhost database connection. Explicit dedicated
  `MONGO_URL`/`MONGO_DATABASE` settings are available.
- Telegram cannot resolve private users by username. Numeric admins register at
  startup; username admins register when a verified private update or signed web
  login supplies their ID. Owners must have initiated a private bot chat. Menu
  failures warn and retry on a later owner update/login, without blocking auth or
  the product handler. The first configured admin remains the primary owner;
  all admins receive authorized access.
- Public URL must be an HTTPS origin with no credentials/path/query/fragment.
  Reverse proxies preserve `/botspot/`. Default listen host is loopback; container
  deployments can configure `HOST=0.0.0.0` behind their TLS proxy.
- The spec explicitly requests HMAC Login Widget auth. Telegram now documents this
  as the [legacy widget](https://core.telegram.org/widgets/login); the newer OIDC
  flow is a separate integration. Browser login requires BotFather domain setup.
  No BotFather changes were made.
- Optional telemetry I/O has one central three-second failure boundary. Errors
  report only their type to stderr, avoiding recursive logging/secrets. Database,
  indexing, registry or menu failures preserve normal bot error handling; the
  heartbeat retries on its next five-minute cycle. Shutdown continues cleanup
  after a failed heartbeat. This follows the existing Whisper telemetry's
  non-breaking write contract without adding handler-local catches.
- Added `testpaths = tests` to `pytest.ini`, matching the existing Makefile and
  pyproject intent. The first exact full command otherwise found seven pre-existing
  failures in archived/manual `dev/` demos (six absent pickle fixtures and one
  unsupported async Telegram demo). That demo body did not execute. No real
  Telegram API calls occurred. The normal fake Telegram helper disables the new
  network-backed component, as it already does for others; explicit observability
  tests verify its enabled lifecycle and default BotManager wiring.
- The spec names no distinct PR title. Use its exact heading:
  **Botspot observability: persistent logs, usage dashboard, owner-only view**.

Validation inspected:

```text
UV_FROZEN=1 uv run pytest -q
335 passed in 5.75s

uv run ruff check <new observability modules, tests, example, journey scripts>
All checks passed!
uv run ruff format --check <same files>
15 files already formatted
git diff --check
exit 0
```

The worktree `.venv` was installed with `uv sync --frozen`; `UV_FROZEN=1` preserves
its lockfile for validation. Sandbox escalation was needed for linked-worktree Git
metadata, dependency downloads and local HTTP/browser binding. No approval review
rejected an action. The first fresh-cache dependency attempt was replaced with
the existing warm cache; no dependency or lockfile changes were required.

Tests include valid/tampered/stale/future Telegram signatures, Unicode/malformed
auth rejection, signed session expiry/revocation, non-owner 403, mock-only private
menu call shapes and command preservation, log/exception redaction, TTL/index
creation, standalone writes, actual aiogram outcomes/error correlation/concurrency,
full aggregation beyond the 200-row display cap, cross-bot isolation, all HTML/JSON
routes and bot registry owner filtering. Lifecycle tests cover startup, mounting,
shutdown, missing configuration, registry/menu outages, username registration and
owner-only command handling before catch-all routers.

Browser evidence: [14 screenshots](../journey/observability/img/),
[walkthrough](../journey/observability/index.html),
[assertions/timing](../journey/observability/evidence.json), and replayable fixture
and capture scripts. Root inspected desktop usage, phone usage, traceback and
filtered logs. Full loop: sign-in → usage/error → traceback → request logs → filters/
sort/expand → owner bots → Usage → Today. No JavaScript errors. All checked phone
usage/log tables fit 366 px inside a 390 px document. Five frictions and fixes are
listed with screenshots in the journey README. Measured fake-Mongo response about
1 ms and DOM about 7 ms; this is not evidence of real-database performance.

Unverified / coordinator boundary:

- Real Mongo persistence, TTL expiry, index/query plans and the **under 500 ms on
  real data** target. Tests use async in-memory Mongo doubles; indexes and bounded
  queries are implemented, but real-load acceptance remains unverified.
- Telegram provider delivery: real Mini App/Login Widget on a configured domain,
  private menu registration, owner command behavior and physical phone experience.
  Cryptographic paths and Bot API call shapes are tested with synthetic data/mocks.
- Whisper / Save As adoption, production registry sharing, consumer dependency
  upgrade, deployment, TLS/proxy configuration and live monitoring.
- Runtime BotFather/domain setup and changing an already-created TTL index's
  retention via Mongo `collMod` belong to deployment review.

This PR does not establish any deployment, live-owner acceptance, or consumer
adoption. The completion marker records the feature commit, PR, test result,
report path, and these unverified boundaries after the branch/PR readback.
