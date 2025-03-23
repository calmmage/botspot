# Auto Archive Demo

This demo shows how to use the Auto Archive component to automatically forward messages to a specified archive chat and delete them from the original conversation.

## Features

- Automatically forward messages to an archive chat
- Delete messages from the original conversation after forwarding
- Control archiving with simple commands
- Configurable delay before message deletion

## Setup

1. Create a new bot using [@BotFather](https://t.me/BotFather) on Telegram
2. Install dependencies:
   ```
   pip install -e .
   ```
3. Copy `sample.env` to `.env` and configure it with your bot token and other settings
4. Run the bot:
   ```
   python bot.py
   ```

## Usage

1. Start the bot by sending `/start` or `/help`
2. Bind an archive chat using the command: `/bind_archive [archive_chat_id]`
   - You can get a chat ID by forwarding a message from the chat to [@userinfobot](https://t.me/userinfobot)
3. Send any message to the bot or the chat where it's active
4. The message will be forwarded to your archive chat and deleted from the original conversation

### Available Commands

- `/bind_archive [chat_id]` - Bind the current chat to an archive chat
- `/unbind_archive` - Remove archive binding for the current chat
- `/toggle_archive` - Temporarily enable/disable archiving without removing the binding

## How It Works

The Auto Archive component:
1. Listens for messages in chats where it's bound
2. Forwards each message to the designated archive chat
3. Deletes the original message after a configurable delay
4. Maintains bindings in MongoDB for persistence

This is useful for creating:
- Chat log bots
- Clean conversation spaces that automatically archive messages
- Self-destructing message channels