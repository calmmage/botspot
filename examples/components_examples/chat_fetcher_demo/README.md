# ChatFetcher Demo Bot

This demo showcases the ChatFetcher component from Botspot, which allows your bot to
access and search Telegram chats and messages.

## Features

- Access user's Telegram chats using Telethon
- List and search chats
- Fetch messages from specific chats
- Search message content
- Cache chats and messages in MongoDB (optional)
- Single user mode support (optional)

## Prerequisites

- Python 3.8+
- Telegram Bot Token
- Telegram API ID and API Hash (from https://my.telegram.org/apps)
- MongoDB (optional, for caching)

## Setup

1. Clone the repository
2. Copy `sample.env` to `.env` and fill in the required values
3. Install dependencies:

```bash
pip install -r requirements.txt  # or use poetry
```

4. Run the bot:

```bash
python bot.py
```

## Usage

1. Start the bot with `/start`
2. Setup your Telethon client with `/setup_telethon`
3. List your chats with `/list_chats`
4. Fetch messages from a chat with `/fetch_messages`
5. Search for specific messages with `/search_messages`

## Component Details

The ChatFetcher component is designed to:

- Use Telethon to access user's Telegram account
- Fetch and search chats and messages
- Cache results in MongoDB for faster access
- Handle pagination and API limitations
- Support single user mode

## Environment Variables

See `sample.env` for all available configuration options.

## Dependencies

- telethon
- motor (MongoDB driver)
- aiogram
- botspot