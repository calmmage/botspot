# Botspot 101: Component Examples

## Utils Components

### send_safe.py
```python
from aiogram.types import Message
from botspot.utils.send_safe import send_safe

async def message_handler(message: Message) -> None:
    long_text: str = "This is a very long message. " * 100
    await send_safe(message.chat.id, long_text)
```

Purpose: Safely sends messages that exceed Telegram's length limits.

## New Components

### chat_fetcher.py
```python
from aiogram.types import Message
from botspot.components.chat_fetcher import get_chat_fetcher

async def fetch_messages(message: Message) -> None:
    user_id: int = message.from_user.id
    chat_id: int = -100123456789
    
    fetcher = get_chat_fetcher()
    messages = await fetcher.get_chat_messages(chat_id, user_id, limit=10)
    
    for msg in messages:
        print(f"Message from {msg.sender_id}: {msg.text}")
```

Purpose: Access message history from chats using Telethon client.

### llm_provider.py
```python
from aiogram.types import Message
from pydantic import BaseModel
from botspot.components.llm_provider import aquery_llm, astream_llm, get_llm_provider

async def llm_example(message: Message) -> None:
    user_id: int = message.from_user.id
    provider = get_llm_provider()
    
    # Text query
    response: str = await aquery_llm(
        prompt=message.text,
        user=user_id,
        model="claude-3.5"
    )
    
    # Streaming response
    async for chunk in astream_llm(prompt="Tell me a story", user=user_id):
        print(chunk, end="")
    
    # Structured output
    class MovieRecommendation(BaseModel):
        title: str
        year: int
        reasons: list[str]
    
    movie: MovieRecommendation = await provider.aquery_llm_structured(
        prompt="Recommend a sci-fi movie",
        output_schema=MovieRecommendation,
        user=user_id
    )
```

Purpose: Interface to query LLMs with support for text, streaming, and structured responses.

### chat_binder.py
```python
from aiogram.types import Message
from botspot.components.chat_binder import bind_chat, get_user_bound_chats

async def bind_example(message: Message) -> None:
    user_id: int = message.from_user.id
    chat_id: int = message.chat.id
    
    record = await bind_chat(user_id, chat_id)
    chats = await get_user_bound_chats(user_id)
```

Purpose: Binds a chat to a user for different interaction contexts.

## Data Components

### mongo_database.py
```python
from botspot.components.data.mongo_database import get_database

async def db_example() -> None:
    db = get_database()
    collection = db["test_collection"]
    await collection.insert_one({"name": "Test User", "created_at": "now"})
    doc = await collection.find_one({"name": "Test User"})
```

Purpose: MongoDB database connectivity for persistent storage.

### user_data.py
```python
from aiogram.types.user import User as AiogramUser
from botspot.components.data.user_data import User, get_user_manager

async def user_example() -> None:
    telegram_user = AiogramUser(id=12345, first_name="John")
    
    user_manager = get_user_manager()
    user = User(user_id=telegram_user.id, first_name=telegram_user.first_name)
    
    await user_manager.add_user(user)
    retrieved_user = await user_manager.get_user(user.user_id)
```

Purpose: User data storage and tracking.

## QOL Components

### bot_commands_menu.py
```python
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from botspot.utils.bot_commands import botspot_command, add_hidden_command

router = Router()

@botspot_command("start", "Start the bot")
@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer("Welcome to the bot!")

@add_hidden_command("secret", "Secret command")
@router.message(Command("secret"))
async def cmd_secret(message: Message) -> None:
    await message.answer("This is a hidden command")
```

Purpose: Command registration and display in Telegram command menu.

### bot_info.py
```python
from aiogram import Dispatcher
from aiogram.filters import Command
from botspot.components.bot_info import bot_info_handler

async def setup_info(dp: Dispatcher) -> None:
    dp.message.register(bot_info_handler, Command("bot_info"))
```

Purpose: Provides bot version, uptime, and enabled components.

## Main Components

### single_user_mode.py
```python
from aiogram import Bot, Dispatcher
from botspot.components.single_user_mode import (
    SingleUserModeSettings, initialize, setup_dispatcher
)

async def setup_single_user() -> None:
    bot = Bot("YOUR_BOT_TOKEN")
    dp = Dispatcher()
    
    settings = SingleUserModeSettings(enabled=True, user="12345")
    initialize(settings)
    setup_dispatcher(dp)
```

Purpose: Restricts bot access to a single specified user.

### queue_manager.py
```python
from aiogram.types import Message
from pydantic import BaseModel
from botspot.components.queue_manager import create_queue, QueueItem

async def queue_example(message: Message) -> None:
    queue = create_queue()
    await queue.add_item(QueueItem(data=message.text), user_id=message.from_user.id)
    
    # With custom model
    class MovieIdea(BaseModel):
        idea: str
        type: str
    
    movie_queue = create_queue("movies", MovieIdea)
    await movie_queue.add_item(
        MovieIdea(idea="Inception", type="specific_movie"), 
        message.from_user.id
    )
```

Purpose: Manages user-specific queues of items.

### user_interactions.py
```python
from typing import Optional
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from botspot.components.features.user_interactions import (
    ask_user, ask_user_choice, ask_user_confirmation, ask_user_raw
)

async def interactions_example(message: Message, state: FSMContext) -> None:
    chat_id: int = message.chat.id
    
    # Basic question
    color: Optional[str] = await ask_user(
        chat_id=chat_id,
        question="What's your favorite color?",
        state=state,
        timeout=60.0
    )
    
    # Multiple choice
    language: Optional[str] = await ask_user_choice(
        chat_id=chat_id,
        question="Select language:",
        choices=["Python", "JavaScript", "Go", "Rust"],
        state=state,
        default_choice="Python"
    )
    
    # Yes/No confirmation
    confirmed: Optional[bool] = await ask_user_confirmation(
        chat_id=chat_id,
        question="Proceed?",
        state=state,
        default_choice=False
    )
    
    # Raw response
    response_msg: Optional[Message] = await ask_user_raw(
        chat_id=chat_id,
        question="Send a photo:",
        state=state
    )
```

Purpose: Interactive conversations with users through questions and choices.

### text_utils.py
```python
from botspot.utils.text_utils import escape_md, split_long_message

original_text: str = "This has *bold* and _italic_ formatting"
escaped_text: str = escape_md(original_text)
print(f"Escaped markdown: {escaped_text}")

long_text: str = "This is a very long message. " * 300
chunks: list[str] = split_long_message(long_text)
```

Purpose: Text manipulation, markdown escaping, splitting long messages.
