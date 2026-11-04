"""Telegram owner authentication and signed, expiring dashboard sessions.

Algorithms: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
and https://core.telegram.org/widgets/login#checking-authorization.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import math
import re
import time
from collections.abc import Mapping
from urllib.parse import parse_qsl

from aiohttp import web

COOKIE_NAME = "botspot_session"
SESSION_PATH = "/botspot/api/session"


class OwnerAuth:
    """Verify Telegram signatures, then apply the existing admin allowlist."""

    def __init__(
        self,
        bot_token: str,
        admins: list[str],
        token: str = "",
        max_age: int = 300,
        session_ttl: int = 86400,
    ):
        self.bot_token = bot_token
        self.admins = {str(a).strip().lstrip("@").lower() for a in admins}
        self.token = token
        self.max_age = max_age
        self.session_ttl = session_ttl
        self.secure_cookies = True
        self.on_owner_authenticated = None
        self._session_key = hmac.digest(bot_token.encode(), b"botspot-session-v1", "sha256")

    def is_owner(self, user: Mapping) -> bool:
        """IDs and Telegram-verified usernames are accepted, never unsigned identity."""
        if not isinstance(user, Mapping):
            return False
        identities = {str(user.get("id", ""))}
        if user.get("username"):
            identities.add(str(user["username"]).lstrip("@").lower())
        return bool((identities - {""}) & self.admins)

    def _fresh(self, auth_date) -> None:
        stamp = int(auth_date)
        age = time.time() - stamp
        if age < -30 or age > self.max_age:
            raise ValueError("Expired Telegram authorization")

    def _owner(self, user: dict) -> dict:
        if not isinstance(user, dict) or not str(user.get("id", "")).isdigit():
            raise ValueError("Missing Telegram user")
        if not self.is_owner(user):
            raise PermissionError("Owner access required")
        return {key: user[key] for key in ("id", "username", "first_name") if key in user}

    def verify_init_data(self, raw: str) -> dict:
        """Validate Mini App HMAC over the decoded fields, excluding only hash."""
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True)
        data = dict(pairs)
        if len(data) != len(pairs):
            raise ValueError("Duplicate Telegram fields")
        received = data.pop("hash", "")
        check = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))
        secret = hmac.digest(b"WebAppData", self.bot_token.encode(), "sha256")
        expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not re.fullmatch(r"[0-9a-f]{64}", received) or not hmac.compare_digest(
            expected, received
        ):
            raise ValueError("Invalid Telegram signature")
        self._fresh(data.get("auth_date", 0))
        return self._owner(json.loads(data.get("user", "{}")))

    def verify_login(self, data: Mapping) -> dict:
        """Validate the browser Login Widget's SHA256-derived HMAC."""
        fields = {key: str(value) for key, value in data.items() if key != "hash"}
        check = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
        secret = hashlib.sha256(self.bot_token.encode()).digest()
        expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        received = data.get("hash", "")
        if (
            not isinstance(received, str)
            or not re.fullmatch(r"[0-9a-f]{64}", received)
            or not hmac.compare_digest(expected, received)
        ):
            raise ValueError("Invalid Telegram signature")
        self._fresh(fields.get("auth_date", 0))
        return self._owner(dict(data))

    def issue_session(self, user: dict) -> str:
        """Sign a minimal owner identity with a server-enforced expiry."""
        identity = (
            self._owner(user)
            if not user.get("token_auth")
            else {"token_auth": hashlib.sha256(self.token.encode()).hexdigest()}
        )
        payload = json.dumps(
            {"user": identity, "expires": int(time.time()) + self.session_ttl},
            separators=(",", ":"),
        ).encode()
        encoded = base64.urlsafe_b64encode(payload).decode().rstrip("=")
        signature = hmac.new(self._session_key, encoded.encode(), hashlib.sha256).hexdigest()
        return f"{encoded}.{signature}"

    def verify_session(self, cookie: str) -> dict | None:
        """Reject expired, altered, and no-longer-admin sessions."""
        if not isinstance(cookie, str):
            return None
        try:
            encoded, signature = cookie.rsplit(".", 1)
            expected = hmac.new(self._session_key, encoded.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, signature):
                return None
            payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
            if not isinstance(payload, dict):
                return None
            expires = payload.get("expires")
            if (
                not isinstance(expires, (int, float))
                or isinstance(expires, bool)
                or not math.isfinite(expires)
                or expires <= time.time()
            ):
                return None
            user = payload["user"]
            if not isinstance(user, dict):
                return None
            if user.get("token_auth"):
                fingerprint = hashlib.sha256(self.token.encode()).hexdigest()
                return (
                    user
                    if self.token and hmac.compare_digest(user["token_auth"], fingerprint)
                    else None
                )
            return self._owner(user)
        except (ValueError, TypeError, KeyError, PermissionError, UnicodeError):
            return None

    def _valid_token(self, value: str) -> bool:
        return bool(
            self.token
            and isinstance(value, str)
            and value
            and hmac.compare_digest(self.token.encode(), value.encode())
        )

    async def authenticate(self, request: web.Request) -> bool:
        """Authenticate every protected route; supplied invalid credentials get 403."""
        authorization = request.headers.get("Authorization", "")
        token = request.headers.get("X-Botspot-Token", "")
        if authorization.startswith("Bearer "):
            token = authorization[7:]
        if token:
            if not self._valid_token(token):
                raise web.HTTPForbidden(text="Owner access required")
            request["botspot_user"] = {"token_auth": True}
            return True
        cookie = request.cookies.get(COOKIE_NAME)
        if cookie:
            user = self.verify_session(cookie)
            if user is None:
                raise web.HTTPForbidden(text="Owner access required")
            request["botspot_user"] = user
            return True
        if authorization:
            raise web.HTTPForbidden(text="Owner access required")
        return False

    async def session_response(self, data: dict, request: web.Request) -> web.Response:
        """Exchange signed Telegram data (or configured fallback token) for a cookie."""
        try:
            if data.get("init_data"):
                user = self.verify_init_data(data["init_data"])
            elif data.get("login"):
                user = self.verify_login(data["login"])
            elif self._valid_token(data.get("token", "")):
                user = {"token_auth": True}
            else:
                raise ValueError("Missing authorization")
        except (ValueError, TypeError, PermissionError, AttributeError):
            raise web.HTTPForbidden(text="Owner access required") from None
        if not user.get("token_auth") and self.on_owner_authenticated is not None:
            await self.on_owner_authenticated(user)
        request["botspot_user"] = user
        response = web.json_response({"ok": True})
        response.set_cookie(
            COOKIE_NAME,
            self.issue_session(user),
            max_age=self.session_ttl,
            httponly=True,
            secure=self.secure_cookies,
            samesite="None" if data.get("init_data") and self.secure_cookies else "Lax",
            path="/botspot",
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    async def session_handler(self, request: web.Request) -> web.Response:
        """Handle the session endpoint without logging credentials."""
        try:
            data = await request.json()
        except (ValueError, TypeError):
            raise web.HTTPForbidden(text="Owner access required") from None
        if not isinstance(data, dict):
            raise web.HTTPForbidden(text="Owner access required")
        return await self.session_response(data, request)


def sign_in_html(bot_username: str = "") -> str:
    """Minimal Mini App / browser Telegram login, with explicit error feedback."""
    username = bot_username.lstrip("@")
    widget = ""
    if re.fullmatch(r"[A-Za-z0-9_]+", username):
        widget = (
            '<script async src="https://telegram.org/js/telegram-widget.js?22" '
            f'data-telegram-login="{html.escape(username, quote=True)}" '
            'data-size="large" data-onauth="telegramLogin(user)"></script>'
        )
    return (
        """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Botspot · Sign in</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;font:15px system-ui;background:#f7f8fa;color:#18212f}main{max-width:360px;padding:24px}h1{font-size:20px}p{color:#667085}form{display:flex;gap:8px;margin-top:20px}input{min-width:0;padding:8px}button{padding:8px}#status{color:#b42318}</style>
</head><body><main><h1>Bot dashboard</h1><p>Sign in as a bot owner.</p>"""
        + widget
        + """
<details><summary>Use a dashboard token</summary><form id="fallback"><input id="token" type="password" aria-label="Dashboard token" required autocomplete="current-password"><button>Open</button></form></details>
<p id="status" role="status"></p></main><script>
async function openSession(data){
  const status=document.getElementById('status');status.textContent='Signing in…';
  try{const response=await fetch('/botspot/api/session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    if(response.ok)location.reload();else status.textContent='Owner access required. Sign in with an admin account.';
  }catch(error){status.textContent='Could not sign in. Please try again.';}
}
function telegramLogin(user){openSession({login:user});}
document.getElementById('fallback').onsubmit=e=>{e.preventDefault();openSession({token:document.getElementById('token').value});};
if(window.Telegram?.WebApp?.initData)openSession({init_data:window.Telegram.WebApp.initData});
</script></body></html>"""
    )
