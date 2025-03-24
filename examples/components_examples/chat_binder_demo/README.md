# Chat Binder Component Demo

This example demonstrates how to use the Chat Binder component to bind chats to users with optional keys.

## Features

- Bind a chat to a user with an optional key
- Unbind a chat from a user
- List all chats bound to a user
- Get a specific bound chat by key
- Echo messages to all bound chats (practical demo feature)

## Requirements

- Python 3.8+
- MongoDB server
- Telegram bot token

## Setup

1. Copy `example.env` to `.env` and fill in your bot token and MongoDB connection details:

```
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

2. Install dependencies using Poetry:

```
poetry install
```

3. Run the bot:

```
poetry run python examples/components_examples/chat_binder_demo/bot.py
```

## Usage

Once the bot is running, you can use the following commands:

- `/start` - Get a welcome message with available commands
- `/bind_chat [key]` - Bind the current chat to you with an optional key (defaults to "default")
- `/unbind_chat [key]` - Unbind the chat from you with the specified key
- `/list_chats` - List all chats bound to you
- `/get_chat [key]` - Get the chat ID for a specific key

Any text messages you send will be echoed to all your bound chats, demonstrating a simple but practical use case for chat binding.

## Configuration Options

The chat_binder component has several configuration options:

```
BOTSPOT_CHAT_BINDER_ENABLED=True  # Enable the component
BOTSPOT_CHAT_BINDER_MONGO_COLLECTION=chat_binder  # MongoDB collection name
BOTSPOT_CHAT_BINDER_COMMANDS_VISIBLE=True  # Show commands in the bot menu
BOTSPOT_CHAT_BINDER_REBIND_MODE=replace  # How to handle rebinding
```

`REBIND_MODE` can be set to one of the `RebindMode` enum values:
- `replace` (default): Replace existing bindings with the same key
- `error`: Raise an error if trying to bind an already bound key
- `ignore`: Keep the existing binding and ignore rebind attempts

## Use Cases

The Chat Binder component can be used for:

1. Automatically forwarding messages to designated chats
2. Creating collection bots that process messages in specific chats
3. Setting up logging/debug channels for your bot
4. Creating auto-archiving functionality for messages
5. Multi-channel message distribution systems