
# Botspot Development Guide

## Build & Test Commands
- Install dependencies: `poetry install`
- Run tests: `poetry run pytest`
- Run single test: `poetry run pytest tests/path_to_test.py::test_function_name -v`
- Format code: `poetry run black .`
- Sort imports: `poetry run isort .`
- Lint code: `poetry run flake8`

## Code Style Guidelines
- **Imports**: Use isort with black profile; line length 100
- **Formatting**: Black with 100 character line length
- **Types**: Use type hints and Pydantic for data models
- **Naming**: snake_case for variables/functions, PascalCase for classes, UPPER_CASE for constants
- **SYSTEM-LEVEL ERROR HANDLING**: DO NOT ADD LOCAL EXCEPTION HANDLERS. THE SYSTEM HAS PROPER ERROR HANDLING WITH LOGGING AND REPORTING
- **Component Usage**: Access components via `deps` object or dedicated getters
- **Documentation**: Docstrings for classes and functions in flake8-docstrings format
- **Dependencies**: Managed with Poetry in pyproject.toml

## Adding New Components
When adding a new component, include:
1. New component file in appropriate subdirectory (main/data/features/middlewares/qol)
2. Add component to config in `core/botspot_settings.py`
3. Add component to `core/dependency_manager.py`
4. Setup component in `core/bot_manager.py`
5. Add getter util to `utils/deps_getters.py` if necessary
6. Create example in `examples/components_examples`, use examples/base_bot - import and reuse.

The codebase is a Telegram bot framework with modular components. Prefer composition over inheritance when extending functionality.

# Botspot Development Guide

## 🔑 Key Principles

1. **EXTREME MINIMALISM**: Delete code ruthlessly. If it works with 3 lines, it doesn't need 10.
2. **USE BOTSPOT DEFAULTS**: Always use base_bot, commands_menu, and default component settings.
3. **ONE FEATURE AT A TIME**: Implement simplest version first, then add minimal integrations.

## 🚫 COMMON MISTAKES TO AVOID

### ❌ Over-engineering
```python
# BAD: Over-engineered approach with unnecessary complexity
async def get_random_item_handler(message: Message):
    if not message.from_user:
        await message.reply("User information is missing.")
        return
    
    user_id = message.from_user.id
    try:
        bindings = await get_chat_binding_status(user_id, message.chat.id)
        if not bindings:
            await message.reply("This chat is not bound to you. Use /bind_chat first.")
            return
        
        try:
            queue = get_queue(f"user_{user_id}")  # WHY USER-SPECIFIC? BAD!
        except KeyError:
            await message.reply("Your queue is empty.")
            return
        
        items = await queue.get_items(str(user_id))  # WHY FILTER BY USER? BAD!
        if not items:
            await message.reply("Your queue is empty.")
            return
        
        random_item = random.choice(items)
        await message.reply(f"Random item from your queue: {random_item.get('data', 'No data')}")
    except Exception as e:
        await message.reply(f"Error getting random item: {str(e)}")
```

### ✅ Minimal Correct Implementation
```python
# GOOD: Minimal implementation that does exactly what's needed
@botspot_command("get_random_item", "Get random item")
@router.message(Command("get_random_item"))
async def get_random_item_handler(message: Message):
    try:
        queue = get_queue()  # Default queue - GOOD!
        items = await queue.get_items()  # All items - GOOD!
        if not items:
            await message.reply("Queue is empty.")
            return
        random_item = random.choice(items)
        await message.reply(f"Random item: {random_item.get('data')}")
    except Exception as e:
        await message.reply(f"Error: {str(e)}")
```

## 📏 IMPLEMENTATION RULES

1. **MAX 10 LINES PER HANDLER** - If longer, you're doing it wrong
2. **USE DEFAULT EVERYTHING**:
    - Default queue key = `"default"`
    - Default item type = `QueueItem`
    - Default MongoDB collection
3. **ALWAYS USE BASE_BOT PATTERN**:
   ```python
   from examples.base_bot import App, main, router
   
   class MyApp(App):
       name = "My App"
   
   # ...handlers...
   
   if __name__ == "__main__":
       main(routers=[router], AppClass=MyApp)
   ```
4. **ALWAYS DECORATE COMMANDS**:
   ```python
   @botspot_command("command_name", "Command description")
   @router.message(Command("command_name"))
   async def command_handler(message: Message):
       # ...
   ```

## 💯 COMPLETE EXAMPLE TEMPLATE

```python
"""
Minimal Queue Manager Demo with Chat Binder
"""

from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message
import random

from botspot.commands_menu import botspot_command
from botspot.components.new.chat_binder import get_binding_records
from botspot.components.new.queue_manager import QueueItem, create_queue, get_queue
from examples.base_bot import App, main, router


class QueueManagerDemoApp(App):
   name = "Queue Manager Demo"


@botspot_command("start", "Start the bot")
@router.message(Command("start"))
async def start_handler(message: Message):
   await message.reply(
      "Queue Manager Demo:\n"
      "- /bind_chat to bind this chat\n"
      "- Send messages to add to queue\n"
      "- /get_random_item to get random item"
   )


@botspot_command("get_random_item", "Get random item")
@router.message(Command("get_random_item"))
async def get_random_item_handler(message: Message):
   try:
      queue = get_queue()
      items = await queue.get_items()
      if not items:
         await message.reply("Queue is empty.")
         return
      random_item = random.choice(items)
      await message.reply(f"Random item: {random_item.get('data')}")
   except Exception as e:
      await message.reply(f"Error: {str(e)}")


@router.message(F.text)
async def message_handler(message: Message):
   if not message.from_user or not message.text or message.text.startswith("/"):
      return

   user_id = message.from_user.id

   # Only process messages in bound chats
   bindings = await get_binding_records(user_id, message.chat.id)
   if not bindings:
      return

   # Add message to queue
   try:
      queue = get_queue()
   except KeyError:
      queue = create_queue()

   item = QueueItem(data=message.text)
   await queue.add_item(item, username=str(user_id))
   await message.reply("Added to queue!")
```

## 🧠 LLM INTERACTION TECHNIQUES

When working with Claude, use these techniques to get better results:

1. **BE EXTREMELY EXPLICIT**: "I want the SIMPLEST implementation possible with DEFAULT queue settings"

2. **USE TEMPLATES**: "Copy this exact structure: [paste minimal template]"

3. **PAIR NEGATIVE/POSITIVE EXAMPLES**: "Don't do X. Do Y instead."

4. **NUMBERED CONSTRAINTS**:
   ```
   Follow these constraints:
   1. Maximum 10 lines per handler
   2. Use default queue settings
   3. No custom user filtering
   ```

5. **ROLE ASSIGNMENT**: "You are SIMPLICITY-BOT. Your purpose is to eliminate all unnecessary code."

6. **CODE REVIEW PROMPT**: "Review this implementation and remove all unnecessary complexity."

## 🧪 VALIDATION CHECKLIST

- [ ] Uses base_bot pattern
- [ ] Uses botspot_command decorator
- [ ] Handlers are ≤10 lines each
- [ ] Uses default queue key
- [ ] Uses default QueueItem type
- [ ] Total code is <100 lines
- [ ] No user-specific filtering of queue items
- [ ] No custom database collections
- [ ] No unnecessary error handling

The entire bot should be focused on just these features:
1. Bind chat with existing /bind_chat command
2. Add messages from bound chats to default queue
3. Get random items from anywhere with /get_random_item

EVERYTHING ELSE IS UNNECESSARY AND SHOULD BE REMOVED.