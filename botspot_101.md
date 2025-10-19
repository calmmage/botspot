# Botspot 101: Core Components

## Message & Command Components

### send_safe.py
```python
from botspot.utils.send_safe import send_safe

await send_safe(chat_id, "Very long message..." * 100)
```

### commands_menu.py
```python
from botspot.commands_menu import botspot_command, add_hidden_command, Visibility
from aiogram.filters import Command

# @botspot_command only adds command to menu - you still need to register the handler!
@botspot_command("start", "Start the bot")
async def cmd_start(message): ...
dp.message.register(cmd_start, Command("start"))

@botspot_command("stats", "Show stats", visibility=Visibility.PUBLIC)
async def cmd_stats(message): ...

@add_hidden_command("debug", "Debug info")
async def cmd_debug(message): ...
```

## Chat Management

### chat_fetcher.py
```python
from botspot import get_chat_fetcher

fetcher = get_chat_fetcher()
history = await fetcher.get_chat_messages(chat_id, user_id, limit=20)
```

### chat_binder.py
```python
from botspot.chat_binder import bind_chat, get_bound_chat, list_user_bindings

await bind_chat(user_id, chat_id)
bound_chat_id = await get_bound_chat(user_id)
bindings = await list_user_bindings(user_id)
```

## LLM Components

### llm_provider.py
```python
from botspot.llm_provider import aquery_llm_text, aquery_llm_structured, astream_llm

# Text response
response = await aquery_llm_text(prompt="Summarize this article", user=user_id)

# Streaming response
async for chunk in astream_llm(prompt="Write a story", user=user_id):
    collected_text += chunk

# Structured output
class Analysis(BaseModel):
    sentiment: str
    key_points: list[str]

result = await aquery_llm_structured(prompt="Analyze this", output_schema=Analysis, user=user_id)
```

## Interactive Components

### user_interactions.py
```python
from botspot.components.features.user_interactions import ask_user, ask_user_choice, ask_user_confirmation

response = await ask_user(chat_id=chat_id, question="What to search?", state=state)
choice = await ask_user_choice(chat_id=chat_id, choices=["News", "Sports"], state=state)
confirmed = await ask_user_confirmation(chat_id=chat_id, question="Proceed?", state=state)
choice = await ask_user_choice(chat_id=chat_id, choices={"1": "News", "2": "Sports"}, state=state)
if choice == "1":
    ...
```

## Data & Access Control

### mongo_database.py
```python
from botspot.components.data.mongo_database import get_database

db = get_database()
await db.users.update_one({"user_id": user_id}, {"$set": data}, upsert=True)
user = await db.users.find_one({"user_id": user_id})
```

### single_user_mode.py
```python
from botspot import is_single_user_mode_enabled, get_single_user

# Check if single user mode is enabled in handlers
if is_single_user_mode_enabled():
    single_user = get_single_user()
    # Work with components without specifying user_id
```

## Using Components in Single User Mode

Single user mode eliminates the need to specify user_id in almost all component interactions:

- **LLM Queries**: Call `aquery_llm_text()` without specifying a user parameter
- **Queue Management**: Add and retrieve items from queues without tracking user_id
- **Chat Binding**: Get bound chats without providing user_id
- **Database Operations**: Store and retrieve user-specific data without explicit filtering
- **Telethon Operations**: Access the user's Telegram account directly

## Error Handling

```python
from botspot.errors import BotspotError

# Never use try/except - let errors bubble up to global handlers!
# Only set params that differ from defaults!
# Only set user_message if user needs to take action!

# Minimal example
raise BotspotError("Data validation failed")

# Action required example
raise BotspotError(
    message="Invalid format",  # error message for logs
    user_message="Please use DD/MM/YYYY format"  # message that will be shown to user
)
```

## Optional Components Worth Knowing

- `botspot/components/main/event_scheduler.py`: toggle timed jobs via `BOTSPOT_SCHEDULER_*`.
- `botspot/components/new/queue_manager.py`: Mongo-backed queues, works with `BOTSPOT_QUEUE_MANAGER_*`.
- `botspot/components/new/auto_archive.py`: archives old dialogs, controlled by `BOTSPOT_AUTO_ARCHIVE_*`.
- `botspot/components/main/trial_mode.py`: gated usage, see `BOTSPOT_TRIAL_MODE_*`.
- `botspot/components/main/telethon_manager.py`: user-client automation, uses `BOTSPOT_TELETHON_MANAGER_*`.
- `botspot/components/new/context_builder.py`, `contact_manager.py`, `subscription_manager.py`, `s3_storage.py`: bring-your-own integrations via matching env prefixes.

## Environment Keys Cheat Sheet

Load them from `.env`; defaults live in `example.env`.

- Core: `TELEGRAM_BOT_TOKEN`, `CALMMAGE_SERVICE_REGISTRY_URL`.
- Access: `BOTSPOT_ADMINS_STR`, `BOTSPOT_FRIENDS_STR`.
- Scheduler: `BOTSPOT_SCHEDULER_ENABLED`, `BOTSPOT_SCHEDULER_TIMEZONE`.
- Mongo: `BOTSPOT_MONGO_DATABASE_ENABLED`, `BOTSPOT_MONGO_DATABASE_CONN_STR`, `BOTSPOT_MONGO_DATABASE_DATABASE`.
- Telethon: `BOTSPOT_TELETHON_MANAGER_ENABLED`, `BOTSPOT_TELETHON_MANAGER_API_ID`, `BOTSPOT_TELETHON_MANAGER_API_HASH`, `BOTSPOT_TELETHON_MANAGER_SESSIONS_DIR`, `BOTSPOT_TELETHON_MANAGER_AUTO_AUTH`.
- Trial mode: `BOTSPOT_TRIAL_MODE_ENABLED`, `BOTSPOT_TRIAL_MODE_PERIOD_PER_USER`, `BOTSPOT_TRIAL_MODE_GLOBAL_PERIOD`, `BOTSPOT_TRIAL_MODE_ALLOWED_USERS`, `BOTSPOT_TRIAL_MODE_LIMIT_PER_USER`, `BOTSPOT_TRIAL_MODE_GLOBAL_LIMIT`.
- User data: `BOTSPOT_USER_DATA_ENABLED`, `BOTSPOT_USER_DATA_MIDDLEWARE_ENABLED`, `BOTSPOT_USER_DATA_COLLECTION`, `BOTSPOT_USER_DATA_CACHE_TTL`, `BOTSPOT_USER_DATA_USER_TYPES_ENABLED`.
- Single user: `BOTSPOT_SINGLE_USER_MODE_ENABLED`, `BOTSPOT_SINGLE_USER_MODE_USER`.
- Send safe: `BOTSPOT_SEND_SAFE_ENABLED`, `BOTSPOT_SEND_SAFE_WRAP_TEXT`, `BOTSPOT_SEND_SAFE_SEND_LONG_MESSAGES_AS_FILES`, `BOTSPOT_SEND_SAFE_SEND_PREVIEW_FOR_LONG_MESSAGES`, `BOTSPOT_SEND_SAFE_PREVIEW_CUTOFF`, `BOTSPOT_SEND_SAFE_WRAP_WIDTH`, `BOTSPOT_SEND_SAFE_PARSE_MODE`.
- Admin filter: `BOTSPOT_ADMIN_FILTER_NOTIFY_BLOCKED`.
- Chat binder: `BOTSPOT_CHAT_BINDER_ENABLED`, `BOTSPOT_CHAT_BINDER_MONGO_COLLECTION`, `BOTSPOT_CHAT_BINDER_COMMANDS_VISIBLE`, `BOTSPOT_CHAT_BINDER_REBIND_MODE`, `BOTSPOT_CHAT_BINDER_CHECK_ACCESS`.
- Chat fetcher: `BOTSPOT_CHAT_FETCHER_ENABLED`, `BOTSPOT_CHAT_FETCHER_DB_CACHE_ENABLED`, `BOTSPOT_CHAT_FETCHER_DEFAULT_DIALOGS_LIMIT`.
- LLM provider: `BOTSPOT_LLM_PROVIDER_ENABLED`, `BOTSPOT_LLM_PROVIDER_DEFAULT_MODEL`, `BOTSPOT_LLM_PROVIDER_DEFAULT_TEMPERATURE`, `BOTSPOT_LLM_PROVIDER_DEFAULT_MAX_TOKENS`, `BOTSPOT_LLM_PROVIDER_DEFAULT_TIMEOUT`, `BOTSPOT_LLM_PROVIDER_ALLOW_EVERYONE`, `BOTSPOT_LLM_PROVIDER_SKIP_IMPORT_CHECK`.
- API keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `XAI_API_KEY`, `DEEPSEEK_API_KEY`, `GOOGLE_API_KEY`, `MISTRAL_API_KEY`, `PERPLEXITY_API_KEY`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`.
- Queue manager: `BOTSPOT_QUEUE_MANAGER_ENABLED`, `BOTSPOT_QUEUE_MANAGER_COLLECTION_NAME_PREFIX`.
- Auto archive: `BOTSPOT_AUTO_ARCHIVE_ENABLED`, `BOTSPOT_AUTO_ARCHIVE_DELAY`, `BOTSPOT_AUTO_ARCHIVE_ENABLE_CHAT_HANDLER`.
- Commands menu: `BOTSPOT_BOT_COMMANDS_MENU_ENABLED`, `BOTSPOT_BOT_COMMANDS_MENU_ADMIN_ID`, `BOTSPOT_BOT_COMMANDS_MENU_ADD_LIST_COMMANDS_HANDLER`, `BOTSPOT_BOT_COMMANDS_MENU_GROUP_DISPLAY_MODE`, `BOTSPOT_BOT_COMMANDS_MENU_DEFAULT_GROUP`, `BOTSPOT_BOT_COMMANDS_MENU_SORT_COMMANDS`.
- Diagnostics: `BOTSPOT_PRINT_BOT_URL_ENABLED`, `BOTSPOT_ERROR_HANDLER_ENABLED`, `BOTSPOT_ERROR_HANDLER_EASTER_EGGS`, `BOTSPOT_ERROR_HANDLER_DEVELOPER_CHAT_ID`, `BOTSPOT_BOT_INFO_ENABLED`, `BOTSPOT_BOT_INFO_HIDE_COMMAND`, `BOTSPOT_BOT_INFO_SHOW_DETAILED_SETTINGS`, `BOTSPOT_ASK_USER_ENABLED`, `BOTSPOT_ASK_USER_DEFAULT_TIMEOUT`.
