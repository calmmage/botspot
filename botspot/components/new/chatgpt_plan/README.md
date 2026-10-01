# chatgpt_plan

Lets a bot user link their own ChatGPT plan ("Sign in with ChatGPT", SIWC) so the
bot's LLM calls run on that plan instead of the bot owner's API key. **Off by default.**
With the flag off, every call raises `PlanDisabled` and does no I/O.

## Eligibility blocker

Self-serve SIWC client IDs are only for open-source, locally hosted apps (loopback
redirect `http://127.0.0.1:{port}/callback`). Paid or remotely hosted bots must apply
through the interest form, <https://openai.com/form/sign-in-with-chatgpt-interest/>,
which is for a "select group of commercial partners". The client ID and the partner
redirect rules come with approval. Until then nothing here can run against OpenAI, so
every endpoint, scope and redirect is configurable.

## What OpenAI allows on the plan path

- OAuth 2 auth-code + PKCE (S256), OIDC. Access token 1 h; refresh token 30 days,
  rolling on each refresh. No client secret.
- Inference: Responses API only (`POST {api_base}/responses`) with `store: false` and
  `stream: true`. Success only after `response.completed`.
- Not allowed: `temperature`, `top_p`, `max_output_tokens`, `metadata`, `user`,
  `previous_response_id`, background mode, hosted tools, function calling, audio/file
  inputs, transcription. `respond()` strips these params before sending.
- Models: per-user catalog, `GET {api_base}/models`, entries with `visibility == "list"`.

## Config (env prefix `BOTSPOT_CHATGPT_PLAN_`)

| Var | Default | Notes |
|---|---|---|
| `ENABLED` | `false` | master flag |
| `CLIENT_ID` | | issued by OpenAI on partner approval |
| `REDIRECT_URI` | | our public HTTPS callback; its path is the mounted route (default `/api/chatgpt/callback`) |
| `TOKEN_ENCRYPTION_KEY` | | Fernet key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `ISSUER` | `https://auth.openai.com` | |
| `AUTHORIZE_PATH` | `/api/accounts/authorize` | |
| `TOKEN_PATH` | `/api/accounts/oauth/token` | |
| `RESOURCE` | `https://api.openai.com/v1` | sent on authorize, code exchange and refresh |
| `API_BASE` | `https://api.openai.com/v1` | |
| `SCOPES` | `openid profile email offline_access resource.invoke chatgpt.tokens.use.direct` | `chatgpt.tokens.use.direct` must be granted |
| `AGENT_NAME_HINT` | | sent on authorize only when set |
| `PENDING_TTL_SECONDS` | `600` | link state lifetime (Mongo TTL index) |
| `REFRESH_MARGIN_SECONDS` | `300` | refresh when the access token expires within this |
| `UNAVAILABLE_RETRIES` | `2` | bounded backoff on 503 / unavailable |
| `UNAVAILABLE_BACKOFF_SECONDS` | `2.0` | doubles per retry |
| `CAP_PAUSE_SECONDS` | `3600` | pause after a 429 that carries no reset hint |
| `REQUEST_TIMEOUT_SECONDS` | `120` | |
| `RETURN_URL` | | optional link on the callback page (e.g. `https://t.me/<bot>`) |

Requires `BOTSPOT_MONGO_DATABASE_ENABLED=true` and the `cryptography` package.
Collections: `chatgpt_oauth_pending` (TTL on `expires_at`), `chatgpt_links` (keyed by
Telegram user id; refresh and access tokens are Fernet-encrypted). Tokens are never logged.

## Usage

```python
from botspot.components.new import chatgpt_plan
from botspot.components.new.chatgpt_plan import PlanNeedsRelink, PlanUnavailable, PlanUsageCapped

url = await chatgpt_plan.start_link(user_id)  # send as an inline URL button
try:
    answer = await chatgpt_plan.respond(user_id, "gpt-6-astra", text, instructions=system)
except (PlanUsageCapped, PlanNeedsRelink, PlanUnavailable):
    ...  # fall back to the normal paid path

# web server (only when enabled)
app.add_routes(chatgpt_plan.aiohttp_routes(chatgpt_plan.get_chatgpt_plan(), on_linked=notify_user))
```

## Error mapping

| OpenAI | Exception | Component action |
|---|---|---|
| 429 / `subscription_sharing_usage_limit_exceeded` | `PlanUsageCapped(reset_hint)` | link status `capped` until the hint (or `CAP_PAUSE_SECONDS`) |
| 401 / `invalid_grant` / `invalid_refresh_token` / `token_expired` | `PlanNeedsRelink` | tokens cleared, status `needs_relink` |
| 503 / `subscription_sharing_usage_unavailable` | `PlanUnavailable` | bounded backoff, then raise |
| 403 (policy / region) | `PlanUnavailable(retryable=False)` | raise, no retry |
| `subscription_sharing_unsupported_capability` | `PlanUnsupported(param)` | drop `error.param` and retry; raise if it can't be dropped |
| no link | `PlanNotLinked` | |
| flag off | `PlanDisabled` | no I/O |

## Untested until OpenAI issues a client ID

All HTTP in the tests is faked. These parts are written from the SIWC docs and have
never talked to OpenAI:

- the real authorize screen, partner redirect rules, and whether `resource` /
  `agent_name_hint` are accepted on each request;
- the token endpoint's exact response shape (`scope`, `id_token`, rolling refresh);
- **id_token signature verification is NOT implemented** (TODO in
  `oauth.verify_id_token_signature`, JWKS). We check `iss`, `aud`, `nonce`, `sub` and
  rely on the token arriving straight from the token endpoint over TLS. Tests inject a
  verifier via `ChatgptPlan(..., id_token_verifier=...)`;
- real Responses stream events, error bodies and the 429 reset hint format;
- `unlink` only deletes our stored tokens; it does not revoke them at OpenAI.
