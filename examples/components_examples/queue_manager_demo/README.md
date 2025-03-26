# Queue Manager Demo with Chat Binder

This example demonstrates the integration of QueueManager and ChatBinder components, allowing users to:

1. Bind chats to their user ID
2. Automatically add messages to a queue when sent in a bound chat
3. Retrieve random items from their queue
4. Check admin status and list chat members

## Features

- Uses chat_binder component to associate chats with users
- Automatically adds messages to user-specific queues
- Demonstrates the Queue Manager's basic functionality
- Shows how to check if a bot is an admin in a chat
- Shows how to retrieve chat member information

## How to Run

1. Copy `sample.env` to `.env` and set your Telegram bot token
2. Make sure MongoDB is running locally or update connection string
3. Run the bot with `python bot.py`

## Bot Commands

- `/start` - Get welcome message and instructions
- `/bind_chat` - Bind the current chat to your user
- `/unbind_chat` - Unbind the current chat
- `/bind_status` - Check if the current chat is bound
- `/get_random_item` - Get a random item from your queue
- `/check_admin` - Check if the bot is an admin in this chat
- `/list_members` - List members in the chat (requires bot to be an admin)

## How it Works

1. When a user binds a chat using `/bind_chat`, the bot establishes a connection between the user ID and chat ID
2. Any text messages sent in that chat are automatically added to the user's queue
3. The `/get_random_item` command retrieves and displays a random item from the queue
4. The bot only processes messages from bound chats

## Integration with Other Components

This example demonstrates how QueueManager can work with other Botspot components like ChatBinder. This pattern can be extended to:

- Use with LLMProvider to process queued messages
- Use with EventScheduler for timed queue processing
- Integrate with TelethonManager for channel/chat interaction