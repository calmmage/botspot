# Chat Binder Component Demo

This example demonstrates how to use the Chat Binder component to bind chats to users with optional keys.

## Features

- Bind a chat to a user with an optional key
- Unbind a chat from a user
- List all chats bound to a user
- Get a specific bound chat by key

## Requirements

- Python 3.8+
- MongoDB server
- Telegram bot token

## Setup

1. Copy `sample.env` to `.env` and fill in your bot token and MongoDB connection details:

```
BOT_TOKEN=your_bot_token_here
MONGO_URI=your_mongodb_uri_here
```

2. Install dependencies using Poetry:

```
poetry install
```

3. Run the bot:

```
poetry run python bot.py
```

## Usage

Once the bot is running, you can use the following commands:

- `/start` - Get a welcome message with available commands
- `/bind_chat [key]` - Bind the current chat to you with an optional key (defaults to "default")
- `/unbind_chat [key]` - Unbind the chat from you with the specified key
- `/list_chats` - List all chats bound to you
- `/get_chat [key]` - Get the chat ID for a specific key

## Use Cases

The Chat Binder component can be used for:

1. Automatically forwarding messages to designated chats
2. Creating collection bots that process messages in specific chats
3. Setting up logging/debug channels for your bot
4. Creating auto-archiving functionality for messages