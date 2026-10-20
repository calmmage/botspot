"""Tests for chatgpt_plan. All HTTP is faked; no client ID, token or network needed."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from aiohttp.test_utils import make_mocked_request
from cryptography.fernet import Fernet

import botspot.components.new.chatgpt_plan as chatgpt_plan
from botspot.components.new.chatgpt_plan import (
    ChatgptPlan,
    ChatgptPlanSettings,
    PlanDisabled,
    PlanError,
    PlanLinkError,
    PlanNeedsRelink,
    PlanNotLinked,
    PlanUnavailable,
    PlanUnsupported,
    PlanUsageCapped,
    aiohttp_routes,
)
from botspot.components.new.chatgpt_plan.client import build_payload, parse_stream
from botspot.components.new.chatgpt_plan.errors import error_from_response
from botspot.components.new.chatgpt_plan.http import AiohttpTransport, HttpResult, parse_sse
from botspot.components.new.chatgpt_plan.settings import (
    LINKS_COLLECTION,
    PENDING_COLLECTION,
    STATUS_CAPPED,
    STATUS_NEEDS_RELINK,
)
from botspot.components.new.chatgpt_plan.store import TokenCipher, utcnow
from botspot.core.errors import ConfigurationError

CLIENT_ID = "app_test_client"
REDIRECT = "https://bot.example.com/api/chatgpt/callback"
USER = 42


# -- fakes --------------------------------------------------------------------


class FakeCollection:
    def __init__(self):
        self.docs: dict = {}
        self.indexes: list = []

    async def create_index(self, keys, **kwargs):
        self.indexes.append((keys, kwargs))

    async def insert_one(self, doc):
        self.docs[doc["_id"]] = dict(doc)

    async def find_one(self, query):
        doc = self.docs.get(query["_id"])
        return dict(doc) if doc else None

    async def find_one_and_delete(self, query):
        return self.docs.pop(query["_id"], None)

    async def delete_one(self, query):
        return SimpleNamespace(deleted_count=int(self.docs.pop(query["_id"], None) is not None))

    async def update_one(self, query, update, upsert=False):
        key = query["_id"]
        if key not in self.docs:
            if not upsert:
                return
            self.docs[key] = {"_id": key}
        self.docs[key].update(update.get("$set", {}))
        for field in update.get("$unset", {}):
            self.docs[key].pop(field, None)


class FakeDb(dict):
    def __missing__(self, name):
        self[name] = FakeCollection()
        return self[name]


class FakeTransport:
    """Queues of HttpResult per method; records every call."""

    def __init__(self):
        self.queues: dict[str, list[HttpResult]] = {"form": [], "get": [], "sse": []}
        self.calls: list[tuple] = []

    def queue(self, method: str, *results: HttpResult):
        self.queues[method].extend(results)

    async def post_form(self, url, form):
        self.calls.append(("form", url, dict(form)))
        return self.queues["form"].pop(0)

    async def get_json(self, url, token):
        self.calls.append(("get", url, token))
        return self.queues["get"].pop(0)

    async def post_sse(self, url, token, payload):
        self.calls.append(("sse", url, token, dict(payload)))
        return self.queues["sse"].pop(0)


class Explode:
    """Any attribute access is a failure: proves no I/O happened."""

    def __getattr__(self, name):
        raise AssertionError(f"unexpected I/O: {name}")

    def __getitem__(self, name):
        raise AssertionError(f"unexpected I/O: {name}")


# -- helpers ------------------------------------------------------------------


def make_settings(**overrides) -> ChatgptPlanSettings:
    values = dict(
        enabled=True,
        client_id=CLIENT_ID,
        redirect_uri=REDIRECT,
        token_encryption_key=Fernet.generate_key().decode(),
        unavailable_backoff_seconds=0,
    )
    values.update(overrides)
    return ChatgptPlanSettings(**values)


def make_plan(verifier=None, **overrides):
    db, transport = FakeDb(), FakeTransport()
    plan = ChatgptPlan(
        make_settings(**overrides), db=db, transport=transport, id_token_verifier=verifier
    )
    return plan, db, transport


async def accept_any(id_token, settings):
    return None


def b64(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


def id_token(**claims) -> str:
    base = {"iss": "https://auth.openai.com", "aud": CLIENT_ID, "sub": "user-sub", "email": "a@b.c"}
    base.update(claims)
    return f"{b64({'alg': 'RS256'})}.{b64(base)}.sig"


def token_body(nonce: str, **overrides) -> dict:
    body = {
        "access_token": "AT-1",
        "refresh_token": "RT-1",
        "expires_in": 3600,
        "scope": "openid email offline_access chatgpt.tokens.use.direct",
        "id_token": id_token(nonce=nonce),
    }
    body.update(overrides)
    return body


def pending_of(db, url: str) -> tuple[str, dict]:
    state = parse_qs(urlparse(url).query)["state"][0]
    return state, db[PENDING_COLLECTION].docs[state]


async def link_user(plan, db, transport, user_id=USER) -> str:
    url = await plan.start_link(user_id)
    state, pending = pending_of(db, url)
    transport.queue("form", HttpResult(200, token_body(pending["nonce"])))
    await plan.complete_link(state, "code-1")
    transport.calls.clear()
    return state


def sse_events(*texts: str, completed=True, model="gpt-6-astra"):
    events = [{"type": "response.output_text.delta", "delta": t} for t in texts]
    if completed:
        usage = {"input_tokens": 3, "output_tokens": 2}
        events.append({"type": "response.completed", "response": {"model": model, "usage": usage}})
    return events


# -- settings + wiring --------------------------------------------------------


def test_settings_off_by_default_and_env_prefix(monkeypatch):
    assert ChatgptPlanSettings().enabled is False
    monkeypatch.setenv("BOTSPOT_CHATGPT_PLAN_ENABLED", "true")
    monkeypatch.setenv("BOTSPOT_CHATGPT_PLAN_CLIENT_ID", "abc")
    monkeypatch.setenv("BOTSPOT_CHATGPT_PLAN_REDIRECT_URI", REDIRECT)
    settings = ChatgptPlanSettings()
    assert settings.enabled and settings.client_id == "abc"
    assert settings.token_url == "https://auth.openai.com/api/accounts/oauth/token"
    assert settings.callback_path == "/api/chatgpt/callback"


def test_botspot_settings_registers_component():
    from botspot.core.botspot_settings import BotspotSettings

    assert BotspotSettings().chatgpt_plan.enabled is False


def test_initialize_requires_mongo_and_client_id():
    from botspot.core.botspot_settings import BotspotSettings
    from botspot.core.dependency_manager import DependencyManager

    DependencyManager(botspot_settings=BotspotSettings())
    with pytest.raises(ConfigurationError):
        chatgpt_plan.initialize(make_settings())


def test_missing_encryption_key_is_configuration_error():
    with pytest.raises(ConfigurationError):
        ChatgptPlan(make_settings(token_encryption_key=None), db=FakeDb())


# -- flag off -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_flag_off_raises_disabled_without_io():
    plan = ChatgptPlan(ChatgptPlanSettings(), db=Explode(), transport=Explode())  # type: ignore[arg-type]
    calls = [
        plan.start_link(USER),
        plan.complete_link("s", "c"),
        plan.get_access_token(USER),
        plan.get_link(USER),
        plan.unlink(USER),
        plan.respond(USER, "m", "hi"),
        plan.list_models(USER),
    ]
    for call in calls:
        with pytest.raises(PlanDisabled):
            await call


@pytest.mark.asyncio
async def test_module_functions_disabled_without_component():
    with pytest.raises(PlanDisabled):
        await chatgpt_plan.start_link(USER)
    with pytest.raises(PlanDisabled):
        await chatgpt_plan.respond(USER, "m", "hi")

    from botspot.core.botspot_settings import BotspotSettings
    from botspot.core.dependency_manager import DependencyManager

    DependencyManager(botspot_settings=BotspotSettings())  # initialized, component off
    with pytest.raises(PlanDisabled):
        await chatgpt_plan.list_models(USER)


@pytest.mark.asyncio
async def test_module_functions_delegate_when_enabled():
    from botspot.core.botspot_settings import BotspotSettings
    from botspot.core.dependency_manager import DependencyManager

    plan, db, transport = make_plan(accept_any)
    DependencyManager(botspot_settings=BotspotSettings()).chatgpt_plan = plan
    await link_user(plan, db, transport)
    assert await chatgpt_plan.get_access_token(USER) == "AT-1"
    assert (await chatgpt_plan.get_link(USER)).email == "a@b.c"
    assert await chatgpt_plan.unlink(USER) is True


# -- link flow ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_authorize_url_params_and_pkce():
    plan, db, _ = make_plan()
    url = await plan.start_link(USER)
    parsed = urlparse(url)
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == (
        "https://auth.openai.com/api/accounts/authorize"
    )
    q = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    assert q["response_type"] == "code"
    assert q["client_id"] == CLIENT_ID
    assert q["redirect_uri"] == REDIRECT
    assert "chatgpt.tokens.use.direct" in q["scope"].split()
    assert q["code_challenge_method"] == "S256"
    assert q["resource"] == "https://api.openai.com/v1"
    assert "agent_name_hint" not in q
    state, pending = pending_of(db, url)
    assert state == q["state"] and pending["nonce"] == q["nonce"]
    assert pending["user_id"] == USER
    verifier = plan.store.cipher.decrypt(pending["code_verifier"])
    digest = hashlib.sha256(verifier.encode()).digest()
    assert q["code_challenge"] == base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    assert db[PENDING_COLLECTION].indexes == [("expires_at", {"expireAfterSeconds": 0})]


@pytest.mark.asyncio
async def test_complete_link_exchanges_code_and_stores_encrypted():
    plan, db, transport = make_plan(accept_any)
    url = await plan.start_link(USER)
    state, pending = pending_of(db, url)
    verifier = plan.store.cipher.decrypt(pending["code_verifier"])
    transport.queue("form", HttpResult(200, token_body(pending["nonce"])))

    result = await plan.complete_link(state, "code-1")

    assert (result.user_id, result.sub, result.email) == (USER, "user-sub", "a@b.c")
    _, url_called, form = transport.calls[0]
    assert url_called == plan.settings.token_url
    assert form == {
        "grant_type": "authorization_code",
        "code": "code-1",
        "redirect_uri": REDIRECT,
        "client_id": CLIENT_ID,
        "code_verifier": verifier,
        "resource": "https://api.openai.com/v1",
    }
    doc = db[LINKS_COLLECTION].docs[USER]
    assert "AT-1" not in json.dumps(doc, default=str)
    assert "RT-1" not in json.dumps(doc, default=str)
    assert plan.store.cipher.decrypt(doc["refresh_token"]) == "RT-1"
    assert doc["status"] == "active" and doc["client_id"] == CLIENT_ID


@pytest.mark.asyncio
async def test_state_is_single_use():
    plan, db, transport = make_plan(accept_any)
    state = await link_user(plan, db, transport)
    with pytest.raises(PlanLinkError):
        await plan.complete_link(state, "code-1")
    assert transport.calls == []


@pytest.mark.asyncio
async def test_expired_state_is_rejected_without_http():
    plan, db, transport = make_plan(accept_any)
    state, pending = pending_of(db, await plan.start_link(USER))
    pending["expires_at"] = utcnow() - timedelta(seconds=1)
    with pytest.raises(PlanLinkError):
        await plan.complete_link(state, "code-1")
    assert transport.calls == []


@pytest.mark.asyncio
async def test_missing_scope_is_rejected():
    plan, db, transport = make_plan(accept_any)
    state, pending = pending_of(db, await plan.start_link(USER))
    body = token_body(pending["nonce"], scope="openid email offline_access")
    transport.queue("form", HttpResult(200, body))
    with pytest.raises(PlanLinkError, match="chatgpt.tokens.use.direct"):
        await plan.complete_link(state, "code-1")
    assert USER not in db[LINKS_COLLECTION].docs


@pytest.mark.parametrize(
    "claims",
    [{"nonce": "wrong"}, {"aud": "someone-else"}, {"iss": "https://evil.example.com"}],
)
@pytest.mark.asyncio
async def test_id_token_claim_checks(claims):
    plan, db, transport = make_plan(accept_any)
    state, pending = pending_of(db, await plan.start_link(USER))
    body = token_body(pending["nonce"], id_token=id_token(**{"nonce": pending["nonce"], **claims}))
    transport.queue("form", HttpResult(200, body))
    with pytest.raises(PlanLinkError):
        await plan.complete_link(state, "code-1")


@pytest.mark.asyncio
async def test_id_token_signature_hook_is_called_and_can_reject():
    seen = []

    async def reject(token, settings):
        seen.append(token)
        raise PlanLinkError("bad signature")

    plan, db, transport = make_plan(reject)
    state, pending = pending_of(db, await plan.start_link(USER))
    body = token_body(pending["nonce"])
    transport.queue("form", HttpResult(200, body))
    with pytest.raises(PlanLinkError, match="bad signature"):
        await plan.complete_link(state, "code-1")
    assert seen == [body["id_token"]]
    assert USER not in db[LINKS_COLLECTION].docs


@pytest.mark.asyncio
async def test_failed_code_exchange_is_link_error():
    plan, db, transport = make_plan(accept_any)
    state, _ = pending_of(db, await plan.start_link(USER))
    transport.queue("form", HttpResult(400, {"error": "invalid_grant"}))
    with pytest.raises(PlanLinkError, match="invalid_grant"):
        await plan.complete_link(state, "code-1")


# -- tokens -------------------------------------------------------------------


def test_encryption_round_trip():
    cipher = TokenCipher(Fernet.generate_key().decode())
    secret = cipher.encrypt("refresh-token-value")
    assert secret != "refresh-token-value"
    assert cipher.decrypt(secret) == "refresh-token-value"
    with pytest.raises(ConfigurationError):
        TokenCipher("")


@pytest.mark.asyncio
async def test_fresh_access_token_needs_no_http():
    plan, db, transport = make_plan(accept_any)
    await link_user(plan, db, transport)
    assert await plan.get_access_token(USER) == "AT-1"
    assert transport.calls == []


@pytest.mark.asyncio
async def test_refresh_is_rolling():
    plan, db, transport = make_plan(accept_any)
    await link_user(plan, db, transport)
    links = db[LINKS_COLLECTION].docs

    links[USER]["expires_at"] = utcnow() + timedelta(seconds=60)  # inside 300 s margin
    transport.queue("form", HttpResult(200, {"access_token": "AT-2", "refresh_token": "RT-2"}))
    assert await plan.get_access_token(USER) == "AT-2"
    assert transport.calls[-1][2]["refresh_token"] == "RT-1"
    assert transport.calls[-1][2]["grant_type"] == "refresh_token"

    links[USER]["expires_at"] = utcnow() - timedelta(seconds=1)
    transport.queue("form", HttpResult(200, {"access_token": "AT-3", "expires_in": 3600}))
    assert await plan.get_access_token(USER) == "AT-3"
    assert transport.calls[-1][2]["refresh_token"] == "RT-2"
    # no new refresh token returned -> the last one is kept
    assert plan.store.cipher.decrypt(links[USER]["refresh_token"]) == "RT-2"


@pytest.mark.parametrize(
    "status,body",
    [
        (400, {"error": "invalid_grant"}),
        (400, {"error": "invalid_refresh_token"}),
        (401, {"error": {"code": "token_expired"}}),
        (401, {}),
    ],
)
@pytest.mark.asyncio
async def test_refresh_failure_marks_needs_relink(status, body):
    plan, db, transport = make_plan(accept_any)
    await link_user(plan, db, transport)
    db[LINKS_COLLECTION].docs[USER]["expires_at"] = utcnow() - timedelta(seconds=1)
    transport.queue("form", HttpResult(status, body))
    with pytest.raises(PlanNeedsRelink):
        await plan.get_access_token(USER)
    doc = db[LINKS_COLLECTION].docs[USER]
    assert doc["status"] == STATUS_NEEDS_RELINK
    assert "refresh_token" not in doc and "access_token" not in doc
    transport.calls.clear()
    with pytest.raises(PlanNeedsRelink):
        await plan.get_access_token(USER)
    assert transport.calls == []


@pytest.mark.asyncio
async def test_not_linked_and_unlink():
    plan, db, transport = make_plan(accept_any)
    with pytest.raises(PlanNotLinked):
        await plan.get_access_token(USER)
    assert await plan.get_link(USER) is None
    await link_user(plan, db, transport)
    assert (await plan.get_link(USER)).status == "active"
    assert await plan.unlink(USER) is True
    assert await plan.unlink(USER) is False


# -- responses ----------------------------------------------------------------


def test_parse_sse():
    lines = [
        'data: {"type": "a"}',
        "",
        "event: x",
        'data: {"type":',
        'data: "b"}',
        "",
        "data: [DONE]",
        "",
    ]
    assert parse_sse(lines) == [{"type": "a"}, {"type": "b"}]


def test_build_payload_strips_disallowed_params():
    payload = build_payload(
        "m", "hi", "be brief", {"temperature": 0.2, "max_output_tokens": 5, "reasoning": {}}
    )
    assert payload == {
        "model": "m",
        "input": "hi",
        "store": False,
        "stream": True,
        "instructions": "be brief",
        "reasoning": {},
    }


def test_parse_stream_requires_completed():
    assert parse_stream(sse_events("Hel", "lo"), "m").text == "Hello"
    with pytest.raises(PlanUnavailable, match="response.completed"):
        parse_stream(sse_events("Hel", completed=False), "m")


def test_parse_stream_falls_back_to_output_items():
    out = [{"content": [{"type": "output_text", "text": "Hi"}]}]
    events = [{"type": "response.completed", "response": {"output": out}}]
    assert parse_stream(events, "m").text == "Hi"


@pytest.mark.asyncio
async def test_respond_streams_on_user_plan():
    plan, db, transport = make_plan(accept_any)
    await link_user(plan, db, transport)
    transport.queue("sse", HttpResult(200, events=sse_events("Hel", "lo")))

    response = await plan.respond(USER, "gpt-6-astra", "hi", instructions="sys", temperature=1)

    assert (response.text, response.model) == ("Hello", "gpt-6-astra")
    assert response.usage == {"input_tokens": 3, "output_tokens": 2}
    _, url, token, payload = transport.calls[0]
    assert url == "https://api.openai.com/v1/responses" and token == "AT-1"
    assert payload["store"] is False and payload["stream"] is True
    assert "temperature" not in payload
    assert db[LINKS_COLLECTION].docs[USER]["last_used_at"] is not None


@pytest.mark.asyncio
async def test_respond_without_completed_is_error():
    plan, db, transport = make_plan(accept_any, unavailable_retries=0)
    await link_user(plan, db, transport)
    transport.queue("sse", HttpResult(200, events=sse_events("partial", completed=False)))
    with pytest.raises(PlanUnavailable):
        await plan.respond(USER, "m", "hi")


@pytest.mark.parametrize(
    "status,body,expected",
    [
        (429, {"error": {"code": "subscription_sharing_usage_limit_exceeded"}}, PlanUsageCapped),
        (429, {}, PlanUsageCapped),
        (401, {"error": {"code": "invalid_api_key"}}, PlanNeedsRelink),
        (400, {"error": "invalid_grant"}, PlanNeedsRelink),
        (400, {"error": "invalid_refresh_token"}, PlanNeedsRelink),
        (401, {"error": {"code": "token_expired"}}, PlanNeedsRelink),
        (403, {"error": {"code": "unsupported_country"}}, PlanUnavailable),
        (503, {"error": {"code": "subscription_sharing_usage_unavailable"}}, PlanUnavailable),
        (
            400,
            {"error": {"code": "subscription_sharing_unsupported_capability", "param": "tools"}},
            PlanUnsupported,
        ),
        (500, None, PlanUnavailable),
    ],
)
def test_error_mapping_table(status, body, expected):
    error = error_from_response(status, body)
    assert type(error) is expected
    assert isinstance(error, PlanError)


def test_error_mapping_details():
    capped = error_from_response(429, {}, {"Retry-After": "120"})
    assert isinstance(capped, PlanUsageCapped) and capped.reset_hint == "120"
    unsupported = error_from_response(
        400, {"error": {"code": "subscription_sharing_unsupported_capability", "param": "tools"}}
    )
    assert isinstance(unsupported, PlanUnsupported) and unsupported.param == "tools"
    forbidden = error_from_response(403, {})
    assert isinstance(forbidden, PlanUnavailable) and forbidden.retryable is False
    assert str(forbidden)


@pytest.mark.asyncio
async def test_respond_429_marks_capped_then_short_circuits():
    plan, db, transport = make_plan(accept_any)
    await link_user(plan, db, transport)
    body = {"error": {"code": "subscription_sharing_usage_limit_exceeded"}}
    transport.queue("sse", HttpResult(429, body, headers={"Retry-After": "600"}))
    with pytest.raises(PlanUsageCapped):
        await plan.respond(USER, "m", "hi")
    doc = db[LINKS_COLLECTION].docs[USER]
    assert doc["status"] == STATUS_CAPPED
    assert doc["capped_until"] > utcnow() + timedelta(seconds=500)
    transport.calls.clear()
    with pytest.raises(PlanUsageCapped):
        await plan.respond(USER, "m", "hi")
    assert transport.calls == []


@pytest.mark.asyncio
async def test_respond_401_marks_needs_relink():
    plan, db, transport = make_plan(accept_any)
    await link_user(plan, db, transport)
    transport.queue("sse", HttpResult(401, {"error": {"code": "token_revoked"}}))
    with pytest.raises(PlanNeedsRelink):
        await plan.respond(USER, "m", "hi")
    assert db[LINKS_COLLECTION].docs[USER]["status"] == STATUS_NEEDS_RELINK


@pytest.mark.asyncio
async def test_respond_stream_failed_event_is_mapped():
    plan, db, transport = make_plan(accept_any)
    await link_user(plan, db, transport)
    failed = {
        "type": "response.failed",
        "response": {"error": {"code": "subscription_sharing_usage_limit_exceeded"}},
    }
    transport.queue("sse", HttpResult(200, events=[failed]))
    with pytest.raises(PlanUsageCapped):
        await plan.respond(USER, "m", "hi")
    assert db[LINKS_COLLECTION].docs[USER]["status"] == STATUS_CAPPED


@pytest.mark.asyncio
async def test_respond_503_backs_off_then_succeeds():
    plan, db, transport = make_plan(accept_any, unavailable_retries=2)
    await link_user(plan, db, transport)
    busy = HttpResult(503, {"error": {"code": "subscription_sharing_usage_unavailable"}})
    transport.queue("sse", busy, busy, HttpResult(200, events=sse_events("ok")))
    assert (await plan.respond(USER, "m", "hi")).text == "ok"
    assert len(transport.calls) == 3


@pytest.mark.asyncio
async def test_respond_503_gives_up_after_bounded_retries():
    plan, db, transport = make_plan(accept_any, unavailable_retries=1)
    await link_user(plan, db, transport)
    busy = HttpResult(503, {})
    transport.queue("sse", busy, busy, busy)
    with pytest.raises(PlanUnavailable):
        await plan.respond(USER, "m", "hi")
    assert len(transport.calls) == 2


@pytest.mark.asyncio
async def test_respond_403_is_not_retried():
    plan, db, transport = make_plan(accept_any, unavailable_retries=3)
    await link_user(plan, db, transport)
    transport.queue("sse", HttpResult(403, {}))
    with pytest.raises(PlanUnavailable):
        await plan.respond(USER, "m", "hi")
    assert len(transport.calls) == 1


@pytest.mark.asyncio
async def test_respond_drops_unsupported_param_and_retries():
    plan, db, transport = make_plan(accept_any)
    await link_user(plan, db, transport)
    unsupported = {
        "error": {"code": "subscription_sharing_unsupported_capability", "param": "reasoning"}
    }
    transport.queue("sse", HttpResult(400, unsupported), HttpResult(200, events=sse_events("ok")))
    response = await plan.respond(USER, "m", "hi", reasoning={"effort": "low"})
    assert response.text == "ok"
    assert "reasoning" in transport.calls[0][3] and "reasoning" not in transport.calls[1][3]


@pytest.mark.asyncio
async def test_respond_unsupported_required_param_raises():
    plan, db, transport = make_plan(accept_any)
    await link_user(plan, db, transport)
    unsupported = {
        "error": {"code": "subscription_sharing_unsupported_capability", "param": "input"}
    }
    transport.queue("sse", HttpResult(400, unsupported))
    with pytest.raises(PlanUnsupported) as info:
        await plan.respond(USER, "m", "hi")
    assert info.value.param == "input"


@pytest.mark.asyncio
async def test_list_models_filters_visibility():
    plan, db, transport = make_plan(accept_any)
    await link_user(plan, db, transport)
    models = [
        {"id": "gpt-6-astra", "visibility": "list"},
        {"id": "hidden", "visibility": "hide"},
        {"id": "gpt-6-mini", "visibility": "list"},
    ]
    transport.queue("get", HttpResult(200, {"data": models}))
    assert await plan.list_models(USER) == ["gpt-6-astra", "gpt-6-mini"]
    assert transport.calls[0][1:] == ("https://api.openai.com/v1/models", "AT-1")


# -- web callback -------------------------------------------------------------


@pytest.mark.asyncio
async def test_callback_route_links_and_notifies():
    plan, db, transport = make_plan(accept_any)
    state, pending = pending_of(db, await plan.start_link(USER))
    transport.queue("form", HttpResult(200, token_body(pending["nonce"])))
    linked = []

    async def on_linked(result):
        linked.append(result.user_id)

    (route,) = aiohttp_routes(plan, on_linked)
    assert route.method == "GET" and route.path == "/api/chatgpt/callback"
    request = make_mocked_request("GET", f"/api/chatgpt/callback?state={state}&code=c")
    response = await route.handler(request)
    assert response.status == 200 and "Linked" in response.text
    assert linked == [USER]


@pytest.mark.parametrize("query", ["state=unknown&code=c", "error=access_denied", ""])
@pytest.mark.asyncio
async def test_callback_route_failures(query):
    plan, _, _ = make_plan(accept_any)
    (route,) = aiohttp_routes(plan)
    response = await route.handler(make_mocked_request("GET", f"/api/chatgpt/callback?{query}"))
    assert response.status == 400 and "Not linked" in response.text


# -- real transport against a local test server -------------------------------


@pytest.mark.asyncio
async def test_aiohttp_transport_against_local_server():
    from aiohttp import web
    from aiohttp.test_utils import TestServer

    async def token(request):
        form = await request.post()
        return web.json_response({"grant_type": form["grant_type"]})

    async def responses(request):
        assert request.headers["Authorization"] == "Bearer tok"
        body = await request.json()
        events = sse_events(body["input"])
        text = "".join(f"data: {json.dumps(e)}\n\n" for e in events) + "data: [DONE]\n\n"
        return web.Response(text=text, content_type="text/event-stream")

    async def models(request):
        return web.json_response({"error": {"code": "token_expired"}}, status=401)

    app = web.Application()
    app.router.add_post("/token", token)
    app.router.add_post("/responses", responses)
    app.router.add_get("/models", models)
    async with TestServer(app) as server:
        transport = AiohttpTransport(timeout_seconds=5)
        form = await transport.post_form(str(server.make_url("/token")), {"grant_type": "x"})
        assert form.ok and form.body == {"grant_type": "x"}
        sse = await transport.post_sse(str(server.make_url("/responses")), "tok", {"input": "yo"})
        assert parse_stream(sse.events, "m").text == "yo"
        bad = await transport.get_json(str(server.make_url("/models")), "tok")
        assert bad.status == 401 and isinstance(
            error_from_response(bad.status, bad.body), PlanNeedsRelink
        )
