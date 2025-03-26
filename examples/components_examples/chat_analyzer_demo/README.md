# Chat Analyzer Demo Bot

This demo showcases the ChatFetcher component from Botspot, focusing on the ability to ingest
and cache chat messages in MongoDB for fast access and analysis.

## Features

- `/ingest [chat_id]` - Load messages from a specific chat into MongoDB cache
- `/stats` - Display statistics from the cached data (message count, chat count, last messages)
- Efficiently downloads only new messages when ingesting a chat
- Uses MongoDB for persistent storage of chat messages

## Prerequisites

- Python 3.8+
- Telegram Bot Token
- Telegram API ID and API Hash (from https://my.telegram.org/apps)
- MongoDB server (required for caching)

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
3. Ingest messages from a chat with `/ingest [chat_id]`
   - This loads messages from the specified chat into MongoDB
   - If the chat was previously ingested, only new messages will be downloaded
4. Get statistics about ingested chats with `/stats`
   - See total message count
   - See last message from each cached chat

## How It Works

The key component used in this bot is `ChatFetcher`, which:

1. Uses Telethon to access the Telegram API
2. Efficiently downloads messages with pagination and rate limiting
3. Stores messages and chat information in MongoDB
4. Provides methods to search and access the cached data

When you use `/ingest`, the bot:
1. Checks if the chat is already in the cache
2. Downloads only new messages that aren't already cached
3. Updates the cache with the new messages

When you use `/stats`, the bot:
1. Queries the MongoDB cache directly
2. Aggregates information about all cached chats
3. Returns statistics without needing to access the Telegram API

## Extending This Demo

This demo can be extended in several ways:

1. Add more advanced analytics using aggregation queries on the MongoDB collection
2. Integrate with LLMProvider to generate summaries of chats
3. Add text analysis features (e.g., word frequency, sentiment analysis)
4. Create a dashboard for visualizing chat statistics

## Environment Variables

See `sample.env` for all available configuration options.

## Dependencies

- telethon
- motor (MongoDB driver)
- aiogram
- botspot