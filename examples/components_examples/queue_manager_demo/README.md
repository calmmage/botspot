# Queue Manager Demo

This example demonstrates the usage of the QueueManager component, which provides functionality for managing queues of items stored in MongoDB.

## Features

- Store items in a queue with a uniform internal interface
- Support for priority queues
- Mark items as done/not done
- Get next item by priority and insertion order
- Get random item from the queue
- Easily create multiple queues for different purposes

## How to Run

1. Copy `sample.env` to `.env` and set your Telegram bot token
2. Make sure MongoDB is running locally or update connection string
3. Run the bot with `python bot.py`

## Example Usage

This demo bot showcases the following functionality:

- Send any message to add it to your personal queue
- Reply to your message with "next" to get the next item from the queue
- Reply to your message with "random" to get a random item from the queue
- Use `/queue_show` to see all items in your queue
- Use `/queue_clear` to clear your queue
- Use `/test_queue` to add 5 test items with different priorities

## Custom Queue Types

You can extend the basic `QueueItem` class to create custom queue types:

```python
from pydantic import BaseModel, Field
from botspot.components.new.queue_manager import QueueItem, get_queue_manager

class TaskItem(QueueItem):
    task_type: str
    assigned_to: Optional[int] = None
    due_date: Optional[datetime] = None

# Later in your code
queue_manager = get_queue_manager()
task_queue = queue_manager.get_queue("tasks", TaskItem)

# Add a task
await task_queue.add_item(TaskItem(
    value="Complete the project report",
    task_type="work",
    due_date=datetime.now() + timedelta(days=7),
    priority=3
))
```

## Integration with Other Components

The QueueManager works well with other Botspot components:

- Use with LLMProvider to process queued messages with AI
- Use with ChatBinder to associate queues with specific chats
- Use with EventScheduler for time-based queue processing