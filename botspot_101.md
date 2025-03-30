# Botspot 101: Component Examples

This file contains minimal examples of how to use each Botspot component.

## Utils Components

### text_utils.py
```python
# Example of escaping markdown text
original_text = "This has *bold* and _italic_ formatting with [links](example.com)"
escaped_text = escape_md(original_text)
print(f"Escaped markdown: {escaped_text}")

# Example of splitting a long message
long_text = "This is a very long message. " * 300
chunks = split_long_message(long_text)
print(f"Split into {len(chunks)} chunks")
```

Purpose: Provides utilities for text manipulation, including markdown escaping and splitting long messages.

### send_safe.py
```python
async def message_handler(message: Message):
    super_long_text = "This is a very long message. " * 100
    await send_safe(message.chat.id, super_long_text)
```

Purpose: Safely sends messages that might exceed Telegram's message length limits by splitting them or sending as files.

## New Components

### chat_fetcher.py
```python
async def fetch_messages(message: Message):
    user_id = message.from_user.id
    chat_id = -100123456789  # Replace with a real group chat ID
    
    # Get chat fetcher and retrieve messages
    fetcher = get_chat_fetcher()
    messages = await fetcher.get_chat_messages(chat_id, user_id, limit=10)
    
    # Print message text from retrieved messages
    for msg in messages:
        print(f"Message from {msg.sender_id}: {msg.text}")
```

Purpose: Allows bots to access message history and content from chats using the Telethon client.

### llm_provider.py
```python
async def llm_message_handler(message: Message):
    prompt = message.text
    user_id = message.from_user.id
    
    # 1. Basic text query
    response = await aquery_llm(
        prompt=prompt,
        user=user_id,
        model="claude-3.5",
        temperature=0.7
    )
    
    # 2. Streaming response (to show output token by token)
    print("Streaming response:")
    async for chunk in astream_llm(
        prompt="Tell me a short story",
        user=user_id
    ):
        print(chunk, end="", flush=True)
    
    # 3. Structured output with Pydantic
    from pydantic import BaseModel
    
    class MovieRecommendation(BaseModel):
        title: str
        year: int
        reasons: list[str]
    
    structured_result = await provider.aquery_llm_structured(
        prompt="Recommend a sci-fi movie",
        output_schema=MovieRecommendation,
        user=user_id
    )
    print(f"Movie: {structured_result.title} ({structured_result.year})")
    
    # 4. Raw response with full details
    raw_response = await provider.aquery_llm_raw(
        prompt="What's the weather like?",
        user=user_id
    )
    print(f"Token usage: {raw_response.usage}")
```

Purpose: Provides an interface to query large language models (LLMs) from different providers (Claude, GPT, etc.) with support for text, streaming, structured, and raw responses.

### chat_binder.py
```python
async def bind_chat_handler(message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Bind the current chat to the user
    record = await bind_chat(user_id, chat_id)
    
    # Get all bound chats for this user
    chats = await get_user_bound_chats(user_id)
    print(f"User {user_id} has {len(chats)} bound chats")
```

Purpose: Binds a chat to a user, allowing the user to interact with the bot in different contexts.

## Data Components

### mongo_database.py
```python
async def simple_db_operation():
    # Get the database instance
    db = get_database()
    
    # Create a test collection and insert a document
    collection = db["test_collection"]
    await collection.insert_one({"name": "Test User", "created_at": "now"})
    
    # Find the document
    doc = await collection.find_one({"name": "Test User"})
    print(f"Found document: {doc}")
```

Purpose: Provides MongoDB database connectivity for other components that need persistent storage.

### user_data.py
```python
async def main():
    # Create a sample user from Telegram user data
    telegram_user = AiogramUser(
        id=12345,
        first_name="John",
        last_name="Doe",
        username="johndoe",
        is_bot=False
    )
    
    # Get user manager
    user_manager = get_user_manager()
    
    # Create a User object from Telegram user data
    user = User(
        user_id=telegram_user.id,
        username=telegram_user.username,
        first_name=telegram_user.first_name,
        last_name=telegram_user.last_name
    )
    
    # Add user to database and retrieve later
    await user_manager.add_user(user)
    retrieved_user = await user_manager.get_user(user.user_id)
```

Purpose: Manages user data storage and tracking, including user types (admin, friend, regular).

## QOL Components

### bot_commands_menu.py
```python
# Register command handlers with decorators
@botspot_command("start", "Start the bot")
@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Welcome to the bot!")

# Add a hidden command
@add_hidden_command("secret", "Secret command")
@router.message(Command("secret"))
async def cmd_secret(message: Message):
    await message.answer("This is a hidden command")
```

Purpose: Manages bot command registration and display in the Telegram command menu.

### bot_info.py
```python
async def main():
    # Create dispatcher and register handler
    dp = Dispatcher()
    dp.message.register(bot_info_handler, Command("bot_info"))
    
    # Simulate bot_info command
    message = Message(text="/bot_info", chat={"id": 123456})
    await bot_info_handler(message)
```

Purpose: Provides information about the bot, including version, uptime, and enabled components.

## Main Components

### single_user_mode.py
```python
async def setup_single_user_bot():
    # Create a bot with single user mode
    bot = Bot("YOUR_BOT_TOKEN")
    dp = Dispatcher()
    
    # Set up single user mode
    settings = SingleUserModeSettings(enabled=True, user="12345")
    initialize(settings)
    setup_dispatcher(dp)
    
    # Register a simple handler
    dp.message.register(message_handler)
```

Purpose: Restricts bot access to a single specified user, ignoring messages from all other users.

### queue_manager.py
```python
# Basic usage
async def message_handler(message: Message):
    queue = create_queue()
    item = QueueItem(data=message.text)
    await queue.add_item(item, user_id=message.from_user.id)
    
    items = await queue.get_items(user_id=message.from_user.id)
    await send_safe(message.chat.id, f"Added to queue! Total items: {len(items)}")
```

```python
# Advanced usage with custom item model
class MovieIdeaType(str, Enum):
    specific_movie = "specific_movie"
    cue = "cue"
    person = "person"

class MovieIdea(BaseModel):
    idea: str
    type: MovieIdeaType
    
async def movie_idea_handler(message: Message):
    movie_queue = create_queue("movies", MovieIdea)
    item = MovieIdea(idea="Inception", type=MovieIdeaType.specific_movie)
    await movie_queue.add_item(item, user_id=message.from_user.id)
```

Purpose: Manages queues of items with user-specific access, supporting both simple and complex item models.

## More components will be added as they are implemented

Each example demonstrates the core functionality of a component in just a few lines of code.