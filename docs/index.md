# Botspot

A collection of cross-integrated utils and components for Telegram bots.

Connect botspot components to an [aiogram](https://docs.aiogram.dev) dispatcher. Featured: `user_data` and `send_safe`. Access components via the singleton `deps` object and `deps_getters`.

## Install

Needs **Python ≥ 3.12** and a bot token from [@BotFather](https://t.me/BotFather).

Clone the [botspot-template](https://github.com/calmmage/botspot-template), copy `example.env`, enable the components you want, then run:

```bash
git clone https://github.com/calmmage/botspot-template.git your-bot-name
cd your-bot-name
cp example.env .env          # set TELEGRAM_BOT_TOKEN
python run.py
```

This library (v0.10.39) is installed from git. The PyPI `botspot` project is an older 0.1.x snapshot:

```bash
uv add git+https://github.com/calmmage/botspot.git
```

See the [README](../README.md#install) for badges, the hero screenshot, and the agents pointer.

## Example

`examples/base_bot` is the default pattern:

```python
from botspot import commands_menu
from botspot.utils import send_safe

@commands_menu.botspot_command("start", "Start the bot")
@router.message(CommandStart())
async def start_handler(message: Message, app: App):
    await send_safe(
        message.chat.id,
        f"Hello, {html.bold(message.from_user.full_name)}!\n"
        f"Welcome to {app.name}!\n"
        f"Use /help to see available commands.",
    )
```

Access components with:

```python
from botspot.utils.deps_getters import get_bot, get_database, get_scheduler
```

More demos: [examples/](https://github.com/calmmage/botspot/tree/main/examples). Agent conventions: [AGENTS.md](../AGENTS.md).

## Components

| Area | Examples |
|------|----------|
| Data | PostgreSQL (preferred for new bots), MongoDB, `user_data`, access control |
| Features | `user_interactions` (`ask_user`), multi-forward |
| Main | Telethon, scheduler, trial / single-user mode |
| QoL | `@botspot_command` menu, bot info, print bot URL |
| New | LLM provider, chat binder, queues, S3, message aggregator |

Enable components in settings / `example.env`. `BotManager` wires them into the dispatcher.

PostgreSQL is optional (`sqlalchemy[asyncio]`, `asyncpg`, `alembic` live in the extras group, same as `pymongo`). Enable with `BOTSPOT_POSTGRES_DATABASE_ENABLED` and `BOTSPOT_POSTGRES_DATABASE_URL` (`postgresql+asyncpg://…`). Apps register models on `botspot.components.data.postgres_database.Base` and point Alembic `target_metadata` at `Base.metadata`. Botspot ships no app tables. Mongo stays available and unchanged.

## Docs in this repo

| | |
|---|---|
| Public README | [../README.md](../README.md) |
| Component demos | [../examples/](../examples/) |
| Agent install / conventions | [../AGENTS.md](../AGENTS.md) |
| Vulnerability reports | [../SECURITY.md](../SECURITY.md) |

Docs stay in this repository and are linked from the README. GitHub Pages is not used.
