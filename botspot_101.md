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

@botspot_command("start", "Start the bot")
async def cmd_start(message): pass

@botspot_command("stats", "Show stats", visibility=Visibility.PUBLIC)
async def cmd_stats(message): pass

@add_hidden_command("debug", "Debug info")
async def cmd_debug(message): pass
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
from botspot.components.features.user_interactions import ask_user, ask_user_choice

response = await ask_user(chat_id=chat_id, question="What to search?", state=state)
choice = await ask_user_choice(chat_id=chat_id, choices=["News", "Sports"], state=state)
confirmed = await ask_user_confirmation(chat_id=chat_id, question="Proceed?", state=state)
choice = await ask_user_choice(chat_id=chat_id, choices={'1':"News", '2':"Sports"], state=state)
if choice == '1':
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
