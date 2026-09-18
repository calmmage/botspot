# Tests

Feature tests drive a real aiogram `Bot` + `Dispatcher` through `tests.telegram.BotClient`.
Outgoing Bot API calls never hit the network: `MockedSession` records them.

```python
from tests.telegram import BotClient

client = BotClient(router)
await client.send("/start")
assert "Hello" in "\n".join(client.texts())
```

- `BotClient.send` / `callback` / `emit_startup` feed Updates the same way polling would.
- `mongo=True` injects `MemoryDatabase` so chat_binder, queue_manager, and auto_archive run without MongoDB.
- Postgres tests use `sqlite+aiosqlite`.
- Do not MagicMock handlers, `initialize()`, or the method under test.

```bash
make test                          # pytest + coverage floor
uv run pytest tests/path.py -v     # one file
```
