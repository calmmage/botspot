"""Local evidence fixture: real routes/auth/aggregation, in-memory Mongo double.

Run from this checkout with test dependencies installed:
  uv run python docs/journey/observability/serve.py
Open http://127.0.0.1:18796/botspot/dashboard and use token ``local``.
No Telegram API calls, credentials, external database, or production data.
"""

import datetime as dt
import runpy
import sys
from pathlib import Path

from aiohttp import web

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from botspot.components.new.observability.auth import OwnerAuth  # noqa: E402
from botspot.components.new.observability.dashboard import aiohttp_routes  # noqa: E402


def fixture_client():
    """Use the same fake Mongo evaluator as the HTTP integration tests."""
    fake = runpy.run_path(str(ROOT / "tests/test_observability_dashboard.py"))
    client = fake["fake_client"]()
    client.bot_name = "example_bot"
    client.dimensions = ("file_kind",)
    now = dt.datetime.now(dt.UTC)
    usages, events, logs, errors = [], [], [], []
    for index in range(77):
        when = now - dt.timedelta(hours=index * 2)
        request_id = f"req-{index:03d}"
        user_id = 1001 + index % 5
        failed = index % 19 == 0
        usages.append(
            {
                "bot": client.bot_name,
                "time": when,
                "kind": "transcription" if index % 4 else "summary",
                "user_id": user_id,
                "chat_id": user_id,
                "request_id": request_id,
                "model": "whisper-1" if index % 4 else "gpt-4.1-mini",
                "file_kind": "voice" if index % 3 else "youtube",
                "minutes": round(1.4 + index % 7 * 1.3, 1),
                "cost": round(0.008 + index % 11 * 0.006, 3),
                "outcome": "error" if failed else "ok",
            }
        )
        events.append(
            {
                "bot": client.bot_name,
                "time": when,
                "started_at": when,
                "finished_at": when + dt.timedelta(milliseconds=125 + index * 3),
                "update_kind": "message",
                "handler": "transcribe",
                "user_id": user_id,
                "chat_id": user_id,
                "latency_ms": 125 + index * 3,
                "outcome": "error" if failed else "ok",
                "request_id": request_id,
            }
        )
        logs.append(
            {
                "bot": client.bot_name,
                "time": when,
                "level": "ERROR" if failed else "INFO",
                "logger": "transcription.download" if failed else "transcription.worker",
                "message": "YouTube download failed: no audio stream"
                if failed
                else "Transcription completed",
                "user_id": user_id,
                "chat_id": user_id,
                "request_id": request_id,
                "exception": "RecordingError: yt-dlp could not find an audio stream"
                if failed
                else None,
            }
        )
        if failed:
            errors.append(
                {
                    "bot": client.bot_name,
                    "time": when,
                    "user_id": user_id,
                    "chat_id": user_id,
                    "request_id": request_id,
                    "error_type": "RecordingError",
                    "error_message": "No audio stream",
                    "traceback": "Traceback (most recent call last):\n  File 'transcription.py', line 42, in download\n    raise RecordingError('No audio stream')\nRecordingError: No audio stream\nyt-dlp stderr: requested format is not available",
                }
            )
    for collection, rows in (
        ("usage", usages),
        ("events", events),
        ("logs", logs),
        ("errors", errors),
    ):
        client.database["botspot_" + collection].rows = rows
    client.registry_database["botspot_bot_registry"].rows = [
        {
            "username": "example_bot",
            "bot_id": 12345,
            "owners": ["id:1"],
            "dashboard_url": "https://example.invalid/botspot/dashboard",
            "version": "0.10.41",
            "host": "local-fixture",
            "last_heartbeat": now,
        },
        {
            "username": "archive_example_bot",
            "bot_id": 12346,
            "owners": ["id:1"],
            "dashboard_url": "https://archive.example.invalid/botspot/dashboard",
            "version": "0.10.41",
            "host": "local-fixture",
            "last_heartbeat": now - dt.timedelta(minutes=3),
        },
        {
            "username": "other_owner_bot",
            "bot_id": 12347,
            "owners": ["id:999"],
            "dashboard_url": "https://other.example.invalid/botspot/dashboard",
            "version": "0.10.41",
            "host": "not-visible",
            "last_heartbeat": now,
        },
    ]
    return client


def create_app():
    client = fixture_client()
    auth = OwnerAuth("12345:fixture-token-not-a-real-bot", ["1"], token="local")
    auth.secure_cookies = False  # Loopback HTTP fixture only; production stays Secure.
    app = web.Application()
    app.add_routes(aiohttp_routes(client, auth))
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="127.0.0.1", port=18796, access_log=None)
