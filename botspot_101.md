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
from typing import Optional
from aiogram.types import Message
from pydantic import BaseModel
from botspot.components.new.llm_provider import (
    # Async utilities
    aquery_llm, astream_llm, aquery_llm_structured, aquery_llm_raw,
    # Sync utilities
    query_llm, query_llm_structured, query_llm_raw,
    # Other utilities
    get_llm_provider, get_llm_usage_stats
)

# Async example (for normal bot handlers)
async def llm_async_example(message: Message) -> None:
    user_id: int = message.from_user.id
    
    # Basic text query (async)
    response: str = await aquery_llm(
        prompt=message.text,
        user=user_id,
        model="claude-3.5"
    )
    
    # Streaming response (async)
    async for chunk in astream_llm(prompt="Tell me a story", user=user_id):
        print(chunk, end="")
    
    # Structured output (async)
    class MovieRecommendation(BaseModel):
        title: str
        year: int
        reasons: list[str]
    
    movie: MovieRecommendation = await aquery_llm_structured(
        prompt="Recommend a sci-fi movie",
        output_schema=MovieRecommendation,
        user=user_id
    )
    
    # Raw response with full metadata (async)
    raw_response = await aquery_llm_raw(
        prompt="What's the weather like?",
        user=user_id,
        model="gpt-4o",
        temperature=0.2
    )

# Synchronous example (for scripts)
def llm_sync_example() -> None:
    user_id: int = 12345
    
    # Basic text query (sync)
    response: str = query_llm(
        prompt="What is the capital of France?",
        user=user_id,
        model="gpt-3.5"
    )
    
    # Structured output (sync)
    class WeatherForecast(BaseModel):
        temperature: float
        conditions: str
        precipitation_chance: float
    
    forecast: WeatherForecast = query_llm_structured(
        prompt="Give me a weather forecast for Paris",
        output_schema=WeatherForecast,
        user=user_id
    )
    
    # Raw response with full metadata (sync)
    raw_response = query_llm_raw(
        prompt="Explain quantum physics",
        user=user_id,
        model="claude-3.7"
    )
```

Purpose: Interface to query LLMs with support for text, streaming, structured responses and usage tracking.

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

### auto_archive.py
```python
from aiogram import Dispatcher
from botspot.components.new.auto_archive import (
    AutoArchiveSettings, initialize, setup_dispatcher
)

async def setup_auto_archive(dp: Dispatcher) -> None:
    # Configure auto-archive to forward messages and delete the original
    settings = AutoArchiveSettings(
        enabled=True,
        delay=10  # seconds before deleting original message
    )
    
    # Initialize and add to dispatcher
    auto_archive = initialize(settings)
    dp.message.middleware(auto_archive)
```

Purpose: Automatically forwards messages to a bound chat and deletes the original after a delay.

### subscription_manager.py
```python
from aiogram import Dispatcher
from botspot.components.new.subscription_manager import (
    SubscriptionManagerSettings, initialize, get_subscription_manager
)

async def setup_subscriptions(dp: Dispatcher) -> None:
    # Configure subscription manager
    settings = SubscriptionManagerSettings(enabled=True)
    
    # Initialize
    subscription_manager = initialize(settings)
    
    # Example usage
    async def check_subscription(user_id: int) -> bool:
        sm = get_subscription_manager()
        # Check if user has active subscription
        return True  # Placeholder for actual implementation
```

Purpose: Manages user subscriptions, payment status, and access levels.

### contact_manager.py
```python
from aiogram import Dispatcher
from botspot.components.new.contact_manager import (
    ContactManagerSettings, initialize, get_contact_manager
)
from botspot.components.data.contact_data import Contact

async def manage_contacts_example() -> None:
    # Configure contact manager
    settings = ContactManagerSettings(enabled=True)
    
    # Initialize
    contact_manager = initialize(settings)
    
    # Example usage
    cm = get_contact_manager()
    
    # Create new contact
    new_contact = Contact(
        name="John Doe",
        phones=["+1234567890"],
        emails=["john@example.com"],
        telegram={"id": 123456789, "username": "johndoe"}
    )
    
    # Add to database (placeholder for actual implementation)
    # await cm.add_contact(new_contact)
```

Purpose: Manages contact information with support for various contact methods.

### context_builder.py
```python
from aiogram.types import Message
from botspot.components.new.context_builder import (
    ContextBuilderSettings, initialize, get_context_builder
)

async def context_builder_example(message: Message) -> None:
    # Configure context builder
    settings = ContextBuilderSettings(enabled=True)
    
    # Initialize
    context_builder = initialize(settings)
    
    # Example usage
    cb = get_context_builder()
    
    # Build context for LLM from message
    # This is a placeholder for actual implementation
    context = {
        "user": message.from_user.full_name,
        "message_history": ["Previous messages would be here"],
        "user_preferences": {"language": "en", "expertise": "beginner"}
    }
```

Purpose: Creates context objects for LLM interactions from user messages and history.

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

### print_bot_url.py
```python
from aiogram import Dispatcher
from botspot.components.qol.print_bot_url import (
    PrintBotUrlSettings, setup_dispatcher
)

async def enable_bot_url_logging(dp: Dispatcher) -> None:
    # Configure settings
    settings = PrintBotUrlSettings(enabled=True)
    
    # Register the startup handler
    setup_dispatcher(dp)
    
    # When the bot starts, it will log:
    # INFO: Bot url: https://t.me/your_bot_username
```

Purpose: Logs the bot's t.me URL during startup for easy access.

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

### event_scheduler.py
```python
from datetime import datetime
from aiogram import Dispatcher
from botspot.components.main.event_scheduler import (
    EventSchedulerSettings, initialize, setup_dispatcher, get_scheduler
)

async def setup_scheduled_tasks(dp: Dispatcher) -> None:
    # Configure scheduler with timezone
    settings = EventSchedulerSettings(
        enabled=True,
        timezone="Europe/London"
    )
    
    # Initialize scheduler and add to dispatcher
    scheduler = initialize(settings)
    setup_dispatcher(dp)
    
    # Add scheduled tasks
    async def daily_report() -> None:
        print(f"Running daily report at {datetime.now()}")
    
    # Example usage
    scheduler = get_scheduler()
    scheduler.add_job(
        daily_report,
        trigger="cron",
        hour=9,
        minute=0,
        id="daily_report"
    )
```

Purpose: Schedules and manages periodic or timed tasks using APScheduler.

### trial_mode.py
```python
from aiogram import Dispatcher, Router
from aiogram.types import Message
from aiogram.filters import Command
from botspot.components.main.trial_mode import (
    TrialModeSettings, setup_dispatcher, add_user_limit, add_global_limit
)

# 1. Setup with middleware for all messages
async def setup_trial_mode(dp: Dispatcher) -> None:
    settings = TrialModeSettings(
        enabled=True,
        allowed_users=["admin1", "admin2"],
        limit_per_user=5,  # 5 uses per user
        global_limit=100,  # 100 uses across all users
        period_per_user=86400,  # 24 hours
        global_period=86400  # 24 hours
    )
    
    setup_dispatcher(dp)

# 2. Decorator approach for specific commands
router = Router()

@add_user_limit(limit=3, period=86400)  # 3 uses per day
@add_global_limit(limit=30, period=86400)  # 30 uses per day across all users
@router.message(Command("analyze"))
async def analyze_command(message: Message) -> None:
    await message.answer("Running expensive analysis...")
```

Purpose: Limits bot usage with per-user and global quotas for trial or freemium bots.

## Features Components

### multi_forward_handler.py
```python
from typing import List
from aiogram.types import Message
from botspot.components.features.multi_forward_handler import setup_dispatcher

async def handle_multiple_messages(messages: List[Message]) -> None:
    # Composing multiple messages into one response
    composed_text = ""
    for msg in messages:
        user_name = msg.from_user.full_name
        timestamp = msg.date.strftime("[%H:%M]")
        composed_text += f"{timestamp} {user_name}:\n{msg.text}\n\n"
    
    # Send as single message or file
    if len(composed_text) > 4000:
        await messages[0].answer_document(
            document=composed_text.encode(),
            caption="Combined messages",
            filename="messages.txt"
        )
    else:
        await messages[0].answer(composed_text)

# Register with dispatcher
def register_multi_forward(dp: Dispatcher) -> None:
    setup_dispatcher(dp)
```

Purpose: Collects multiple sequential messages and processes them as a batch.

## Middlewares Components

### error_handler.py
```python
from aiogram import Dispatcher
from botspot.components.middlewares.error_handler import (
    ErrorHandlerSettings, setup_dispatcher
)
from botspot.core.errors import BotspotError

# Custom error with user-friendly message
class PaymentError(BotspotError):
    def __init__(self, message: str = "Payment processing failed"):
        super().__init__(
            user_message=message,
            easter_eggs=True,  # Show easter egg in response
            report_to_dev=True,  # Send report to developer
            include_traceback=True  # Include traceback in developer report
        )

# Set up error handling
async def setup_error_handling(dp: Dispatcher) -> None:
    settings = ErrorHandlerSettings(
        enabled=True,
        easter_eggs=True,
        developer_chat_id=12345678  # Your developer chat ID
    )
    
    # Register error handler with dispatcher
    setup_dispatcher(dp)
    
    # Usage example
    async def risky_function():
        try:
            # Some code that might fail
            result = 1 / 0
        except Exception as e:
            # Raise custom BotspotError
            raise PaymentError("Sorry, we couldn't process your payment") from e
```

Purpose: Handles exceptions with user-friendly messages and developer notifications.
