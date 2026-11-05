# Owner dashboard journey

Local fake-Mongo evidence only, captured from this feature's renderer at desktop
1440×1000 and phone 390×844. No Telegram API, production data or external Mongo.
See [the screenshot walkthrough](index.html) and [machine assertions](evidence.json).

```sh
PYTHONPATH=. uv run python docs/journey/observability/serve.py
# Separate terminal, browser runtime supplied by the task spec:
PYTHONPATH=. ~/calm/framework/tools/calm-env/.venv/bin/python docs/journey/observability/capture.py
```

Preview: `http://127.0.0.1:18796/botspot/dashboard`, local fixture token `local`.
The fixture alone disables Secure cookies for loopback HTTP. It uses the real
routes, signed-session implementation, renderer, and queries over an in-memory
Mongo expression evaluator shared with HTTP tests. Telegram browser scripts are
blocked during capture; live Telegram authentication is covered with signed test
vectors, not a provider/browser login.

Screens contain 77 product events over seven UTC dates, five users, two models,
request events, failed downloads with traceback, logs, and a registry containing
two owner bots plus an excluded outsider. The fixture clock is sampled on server
start. Fake-Mongo navigation timings (about 1 ms response, 7 ms DOM) cannot prove
the real-data 500 ms target.

| Opens / taps | Sees / gets | Phone | Desktop |
|---|---|---|---|
| Dashboard link | Owner sign-in | [01](img/phone-01-sign-in.png) | [01](img/desktop-01-sign-in.png) |
| Wrong token | Explicit owner-access error | [02](img/phone-02-wrong-token.png) | [02](img/desktop-02-wrong-token.png) |
| Correct local token | Usage, ranges, newest-first groups, three rows + more | [03](img/phone-03-usage.png) | [03](img/desktop-03-usage.png) |
| Error count → error | Traceback, × / Esc close | [04](img/phone-04-traceback.png) | [04](img/desktop-04-traceback.png) |
| Request Logs link | Only correlated request's records | [05](img/phone-05-request-logs.png) | [05](img/desktop-05-request-logs.png) |
| Clear → ERROR / YouTube → Filter → sort / more | Matching newest logs | [06](img/phone-06-filtered-logs.png) | [06](img/desktop-06-filtered-logs.png) |
| Bots → Usage → Today | Owner bots only; return to current UTC day | [07](img/phone-07-bots.png) | [07](img/desktop-07-bots.png) |

Top five frictions fixed and captured:

1. Unauthenticated page previously would be raw denial: sign-in now gives Telegram
   entry points plus token fallback, with explicit wrong-account/token feedback.
2. Phone product rows exceeded their wrapper by 10 px: minute-resolution display
   timestamps now fit; full UTC values remain in details and sort keys. All usage
   and logs tables measured 366/366 px, document 390/390 px.
3. Error totals could diverge from failed-product totals: the independent error
   count is a link directly to the error archive.
4. Folded days could hide today's rows / shortened timestamps sort ambiguously:
   newest day first and sorting uses full UTC datetime values.
5. Request links could lose older logs under the default seven-day filter:
   links keep the exact request ID across a bounded 365-day search; registry and
   request pages retain Usage/Logs/Bots navigation back to the same bot.

Checks also exercised both dialog close controls, literal log text, expandable
rows, header sorting, JSON auth guard, hidden outsider bot, and no JavaScript errors.
Provider Telegram Login/Mini App, real Mongo TTL expiry/query plans, device tests,
consumer adoption and deployment remain unverified/out of scope.
