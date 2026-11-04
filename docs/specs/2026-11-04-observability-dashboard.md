# Botspot observability: persistent logs, usage dashboard, owner-only view

Spec written 4 Nov 2026 (Claude, from Petr's request). Builder: Codex via Orca.

## Petr's words

4 Nov 2026:

> do we have logs? - if not, let's ALSO make sure to build and deploy full-fledged logging system
> find the recent chat where i was building usage dashboard and logging and make it so that our botspot library has them and auto-registers them in the account and allows view for authenticated via telegram bot owner

3 Nov 2026 (Grok chat `aca80726-c5de-49b6-94c4-51fed931e3b4`, the chat that started the Whisper dashboard):

> set up proper montitoring dashboard and logging - so that we have all this persistently in a db / web interface, not through just telegram message history..
> I want product-oriented usage metrics and analytics!!

## Why

4 Nov: a public YouTube link failed in both Whisper and Save As, and neither bot kept a record of it. Whisper's prod logs are Coolify container stdout (about 3000 lines, gone on redeploy). Whisper's YouTube path raises `RecordingError` without logging yt-dlp's stderr. Save As logs exist only in `docker logs` on the NAS.

## Starting point: the Whisper version (port it, don't reinvent)

Whisper already has this for one bot, on `origin/dev` of `calmmage/whisper-bot` (commit `8389c76`, release PR #95 is still open):

- `src/usage_log.py`: Mongo collections `usage` (one row per request: user, chat, message, minutes, outcome, cost, model, stage, error) and `errors` (admin error cards with traceback).
- `src/usage_dashboard.py`: `/dashboard/usage` HTML + `/api/dashboard/usage?days=7` JSON. Ranges Today/7/30/90; totals line; By day, By file, By model, By user; requests; errors with traceback dialog. Mobile layout checked at 390 px.
- Journey and screenshots: `docs/journey/usage-dashboard/README.md`.
- Auth today: shared `WEB_DASHBOARD_TOKEN` cookie. Replace it with Telegram owner auth (below), keep the token as a fallback.

Read those files with `git -C /Users/petrlavrov/calm/projects/p-whisper-bot show origin/dev:<path>`. Move the generic parts into botspot; keep Whisper-specific columns (minutes, file kind) as a per-bot extension.

## What to build in botspot

A component, e.g. `botspot/components/new/observability/`, on by default (`BOTSPOT_OBSERVABILITY_ENABLED=true`), settings under `BOTSPOT_OBSERVABILITY_*`, wired like other components in `botspot_settings.py` and `bot_manager.py`.

1. **Persistent logs.** A loguru sink that writes INFO+ records to Mongo `botspot_logs` (time, level, logger, message, bot, request id, user id, chat id, exception text). TTL index, default 30 days. Never log tokens, keys or signed URLs; reuse any existing redaction helpers.
2. **Request events.** Middleware that writes one `botspot_events` row per handled update: update kind, handler, user, chat, started/finished, latency, outcome (`ok` / `error` / `ignored`), error type, request id. The request id is attached to log records in the same update, so one request's logs open from its row.
3. **Errors.** The existing `error_handler` component also writes the error with its traceback and request id to `botspot_errors`. Telegram admin alerts keep working.
4. **Product metrics API.** `record_usage(kind, **fields)` that bots call for product events (Whisper: minutes, cost, model). The dashboard groups by day / user / kind / model automatically.
5. **Dashboard.** aiohttp routes mounted on the bot's existing web server, or a small built-in one when the bot has none (`BOTSPOT_OBSERVABILITY_PORT`):
   - `/botspot/dashboard`: usage (port the Whisper layout and its 5 fixes: phone 390 px, newest first, error count links to errors, traceback dialog with ×/Esc).
   - `/botspot/logs`: filter by level, text, user, request id, time. Newest first. Sortable columns.
   - JSON twins under `/botspot/api/...`.
   - Follow `~/calm/skills` craft rules: `craft:design-code`, `dev:grouping-items`, tables sortable and quiet, page under 500 ms on real data with indexes.
6. **Owner auth through Telegram.**
   - Owner = Telegram user ids/usernames in existing `BOTSPOT_ADMINS` (first admin is the owner).
   - Inside Telegram: a Mini App (WebApp) button. Verify `initData` with the bot token (HMAC-SHA256 per Telegram docs), check `auth_date` freshness, then set a signed session cookie.
   - In a browser: Telegram Login Widget, same verification, same cookie.
   - Anyone not in admins gets 403. The shared token stays as a fallback for scripts (`BOTSPOT_OBSERVABILITY_TOKEN`).
7. **Auto-registration in the bot account.** On startup, when `BOTSPOT_OBSERVABILITY_PUBLIC_URL` is set (HTTPS):
   - `setChatMenuButton` for each owner's private chat only → web app "Dashboard" (other users keep the default menu).
   - an owner-scoped `/dashboard` and `/logs` command (`BotCommandScopeChat`) that replies with the Mini App button.
   - Upsert the bot into a shared Mongo collection `botspot_bot_registry` (username, bot id, dashboard URL, version, host, last heartbeat every 5 min). Use the database from `BOTSPOT_OBSERVABILITY_REGISTRY_MONGO_*` if set, else the bot's own database. A `/botspot/bots` page lists every registered bot with its link and last heartbeat.
   - Without a public URL: logs and events still go to Mongo, and the startup log says why the button wasn't registered.
8. **Standalone writer for non-botspot bots.** Save As is kurigram, not aiogram. Expose `botspot.observability.client` (plain Python: `log_sink(mongo_url, bot_name)`, `record_event(...)`, `record_usage(...)`) so it can write to the same collections without the dispatcher. The dashboard reads those rows the same way.

## Rules

- Work only in your Orca worktree of `calmmage/botspot`. Branch from `origin/dev` (`dev` is the working branch; `main` is the release branch).
- Commit locally, then push your branch and open a PR into `dev`. Never push to `main`/`dev` directly. Never merge.
- Tests: `uv run pytest -q` must pass. Add tests for: initData/Login verification (valid, tampered, stale), non-owner 403, menu-button registration call shape (mock bot), log sink redaction, TTL index creation, event middleware outcome rows, standalone client.
- Use your own harness subagents for parallel parts (auth, dashboard, middleware).
- No Telegram sends to real users, no production deploys, no key reads beyond what tests need. Don't touch `~/calm/notes`.
- Write `docs/specs/2026-11-04-observability-dashboard.REPORT.md` in your branch: what was built, test output, screenshots of the dashboard rendered with fake Mongo at 390 px and desktop (Playwright: `dev:playwright` skill or `~/calm/framework/tools/calm-env/.venv/bin/python`), what's unverified.
- When finished, write `/Users/petrlavrov/calm/state/bot-observability-20261104/botspot.DONE.json` with `{branch, pr_url, commit, tests, report_path, unverified}`.

## Out of scope (Claude does these after review)

Adopting it in Whisper and Save As, deploying, flipping Coolify env.
