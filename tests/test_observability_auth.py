"""Owner authentication without network access or real Telegram credentials."""

import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock
from urllib.parse import urlencode

import pytest
from aiogram.types import BotCommand, BotCommandScopeChat, MenuButtonWebApp
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from botspot.components.new.observability.auth import COOKIE_NAME, OwnerAuth, sign_in_html
from botspot.components.new.observability.registration import dashboard_url, register_owner_menu

TOKEN = "123456789:AATestingTokenForBotspotNotReal"
USER = {"id": 42, "username": "owner", "first_name": "Owner"}


def init_data(user=None, stamp=None, **extra):
    fields = {
        "user": json.dumps(USER if user is None else user),
        "auth_date": str(int(time.time()) if stamp is None else stamp),
        **extra,
    }
    check = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret = hmac.digest(b"WebAppData", TOKEN.encode(), "sha256")
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def login_data(user=None, stamp=None):
    fields = {
        **(USER if user is None else user),
        "auth_date": int(time.time()) if stamp is None else stamp,
    }
    check = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret = hashlib.sha256(TOKEN.encode()).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return fields


@pytest.fixture
def auth():
    return OwnerAuth(TOKEN, ["42"], token="test-dashboard-token")


@pytest.mark.parametrize(
    "method,data", [("verify_init_data", init_data), ("verify_login", login_data)]
)
def test_telegram_valid(auth, method, data):
    assert getattr(auth, method)(data()) == USER


@pytest.mark.parametrize(
    "method,data", [("verify_init_data", init_data), ("verify_login", login_data)]
)
def test_telegram_rejects_stale_and_future(auth, method, data):
    for stamp in [int(time.time()) - 301, int(time.time()) + 60]:
        with pytest.raises(ValueError, match="Expired"):
            getattr(auth, method)(data(stamp=stamp))


def test_tampered_init_data(auth):
    with pytest.raises(ValueError, match="signature"):
        auth.verify_init_data(init_data().replace("owner", "other"))


def test_tampered_login(auth):
    data = login_data()
    data["id"] = 999
    with pytest.raises(ValueError, match="signature"):
        auth.verify_login(data)


def test_init_data_rejects_duplicate_fields(auth):
    with pytest.raises(ValueError, match="Duplicate"):
        auth.verify_init_data(init_data() + "&auth_date=1")


def test_init_data_signs_extra_fields_including_signature(auth):
    assert auth.verify_init_data(init_data(signature="telegram-ed25519-value")) == USER


def test_verified_username_admin_is_case_insensitive():
    auth = OwnerAuth(TOKEN, ["@OwNeR"])
    assert auth.verify_login(login_data()) == USER
    assert not auth.is_owner({"id": 999, "username": "unknown"})


@pytest.mark.parametrize(
    "method,data", [("verify_init_data", init_data), ("verify_login", login_data)]
)
def test_telegram_nonowner(auth, method, data):
    with pytest.raises(PermissionError):
        getattr(auth, method)(data(user={"id": 999, "username": "visitor"}))


def test_sessions_are_signed_expiring_and_recheck_admins(auth, monkeypatch):
    cookie = auth.issue_session(USER)
    assert auth.verify_session(cookie) == USER
    assert auth.verify_session(cookie + "a") is None
    assert auth.verify_session("garbage") is None
    auth.admins.clear()
    assert auth.verify_session(cookie) is None
    auth.admins.add("42")
    now = time.time()
    monkeypatch.setattr(time, "time", lambda: now + auth.session_ttl + 1)
    assert auth.verify_session(cookie) is None


@pytest.mark.asyncio
async def test_authenticate_absent_valid_and_invalid(auth):
    request = make_mocked_request("GET", "/botspot/dashboard")
    assert not await auth.authenticate(request)
    request = make_mocked_request(
        "GET", "/botspot/dashboard", headers={"Cookie": f"{COOKIE_NAME}={auth.issue_session(USER)}"}
    )
    assert await auth.authenticate(request)
    assert request["botspot_user"] == USER
    request = make_mocked_request(
        "GET", "/botspot/api/logs", headers={"Cookie": f"{COOKIE_NAME}=invalid"}
    )
    with pytest.raises(web.HTTPForbidden):
        await auth.authenticate(request)


@pytest.mark.asyncio
async def test_token_fallback_and_session_revocation(auth):
    request = make_mocked_request(
        "GET", "/botspot/api/logs", headers={"Authorization": "Bearer test-dashboard-token"}
    )
    assert await auth.authenticate(request)
    assert request["botspot_user"] == {"token_auth": True}
    request = make_mocked_request(
        "GET", "/botspot/api/logs", headers={"Authorization": "Bearer wrong"}
    )
    with pytest.raises(web.HTTPForbidden):
        await auth.authenticate(request)
    cookie = auth.issue_session({"token_auth": True})
    assert auth.verify_session(cookie)
    auth.token = "replacement"
    assert auth.verify_session(cookie) is None


@pytest.mark.parametrize(
    "body",
    [
        {"init_data": init_data(user={"id": 999})},
        {"login": login_data(user={"id": 999})},
        {"token": "wrong"},
        {},
    ],
)
@pytest.mark.asyncio
async def test_nonowner_session_gets_403(auth, body):
    request = make_mocked_request("POST", "/botspot/api/session")
    with pytest.raises(web.HTTPForbidden):
        await auth.session_response(body, request)


@pytest.mark.asyncio
async def test_successful_session_cookie_security(auth):
    request = make_mocked_request("POST", "/botspot/api/session")
    response = await auth.session_response({"init_data": init_data()}, request)
    assert response.status == 200
    cookie = response.cookies[COOKIE_NAME]
    assert cookie["secure"] and cookie["httponly"]
    assert cookie["samesite"] == "None" and cookie["path"] == "/botspot"
    assert response.headers["Cache-Control"] == "no-store"
    assert auth.verify_session(cookie.value) == USER


@pytest.mark.asyncio
async def test_owner_menu_is_private_and_preserves_commands():
    bot = AsyncMock()
    bot.get_my_commands.return_value = [BotCommand(command="help", description="Help")]
    await register_owner_menu(bot, ["42", "@username", "42"], "https://bot.example")
    bot.set_chat_menu_button.assert_awaited_once()
    kwargs = bot.set_chat_menu_button.call_args.kwargs
    assert kwargs["chat_id"] == 42
    assert isinstance(kwargs["menu_button"], MenuButtonWebApp)
    assert kwargs["menu_button"].web_app.url == "https://bot.example/botspot/dashboard"
    call = bot.set_my_commands.call_args.kwargs
    assert isinstance(call["scope"], BotCommandScopeChat)
    assert call["scope"].chat_id == 42
    assert [command.command for command in call["commands"]] == ["help", "dashboard", "logs"]
    assert not bot.send_message.called


@pytest.mark.asyncio
async def test_owner_menu_inherits_defaults_when_chat_scope_empty():
    bot = AsyncMock()
    bot.get_my_commands.side_effect = [[], [], [BotCommand(command="start", description="Start")]]
    await register_owner_menu(bot, [42], "https://bot.example")
    assert bot.set_my_commands.call_args.kwargs["commands"][0].command == "start"


@pytest.mark.parametrize(
    "url",
    [
        "http://bot.example",
        "https://user:pass@bot.example",
        "https://bot.example?secret=1",
        "https://bot.example/#fragment",
        "https://bot.example/prefix",
        "https://",
    ],
)
def test_public_url_requires_safe_https(url):
    with pytest.raises(ValueError):
        dashboard_url(url)


def test_sign_in_has_both_telegram_entry_points():
    page = sign_in_html("test_bot")
    assert 'data-telegram-login="test_bot"' in page
    assert "WebApp.initData" in page
    assert "initDataUnsafe" not in page
    assert "data-telegram-login=" not in sign_in_html('"><script>alert(1)</script>')


@pytest.mark.asyncio
async def test_nonascii_token_is_forbidden_instead_of_server_error(auth):
    request = make_mocked_request(
        "GET", "/botspot/api/logs", headers={"Authorization": "Bearer not-a-token-å"}
    )
    with pytest.raises(web.HTTPForbidden):
        await auth.authenticate(request)


@pytest.mark.asyncio
async def test_verified_owner_callback_only_runs_for_valid_telegram_auth(auth):
    auth.on_owner_authenticated = AsyncMock()
    request = make_mocked_request("POST", "/botspot/api/session")
    await auth.session_response({"login": login_data()}, request)
    auth.on_owner_authenticated.assert_awaited_once_with(USER)
    auth.on_owner_authenticated.reset_mock()
    await auth.session_response({"token": "test-dashboard-token"}, request)
    with pytest.raises(web.HTTPForbidden):
        await auth.session_response({"login": login_data(user={"id": 999})}, request)
    auth.on_owner_authenticated.assert_not_awaited()


@pytest.mark.asyncio
async def test_widget_sessions_use_lax_cookie_and_local_preview_remains_possible(auth):
    request = make_mocked_request("POST", "/botspot/api/session")
    response = await auth.session_response({"login": login_data()}, request)
    assert response.cookies[COOKIE_NAME]["samesite"] == "Lax"
    auth.secure_cookies = False
    response = await auth.session_response({"init_data": init_data()}, request)
    assert response.cookies[COOKIE_NAME]["samesite"] == "Lax"
    assert not response.cookies[COOKIE_NAME]["secure"]


def test_sessions_reject_malformed_types_even_when_signed(auth):
    import base64

    for payload in [
        None,
        [],
        {"expires": "tomorrow", "user": USER},
        {"expires": float("nan"), "user": USER},
        {"expires": time.time() + 10, "user": []},
    ]:
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        signature = hmac.new(auth._session_key, encoded.encode(), hashlib.sha256).hexdigest()
        assert auth.verify_session(f"{encoded}.{signature}") is None
    assert auth.verify_session(None) is None


def test_nonascii_telegram_hash_is_invalid(auth):
    with pytest.raises(ValueError, match="signature"):
        auth.verify_init_data("hash=å")
    with pytest.raises(ValueError, match="signature"):
        auth.verify_login({"hash": "å"})
