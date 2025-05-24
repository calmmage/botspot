# Queue Manager

- **Main Feature**: Stores items in a MongoDB collection with a uniform internal interface for integrations.
- **Demo Bot**: Send any message; it's auto-added to the queue. Reply with "next" to pull the next item.
- **Useful Bot**: **Task Queue Bot** - Auto-queues messages or tasks, processes them in order or randomly, and integrates with other components (e.g., LLM parsing).

Important: for example bot, look how other bots are implemented. Use botspot features by enabling them with env vars. Use base_bot as foundation. 

## Developer Notes

1) there is already an implementation - will do a second iteration now

2) there's a clear issue - too much garbage fields + no integration with pydantic, fix that

3) final desired interface is something like get_queue() and add_queue(). with no parameters they should still work - assuming trivial pydantic item type - just a single str field - and default queue key.

4) the basic implementation would be something like a simple bot which you do /bind and it binds chat to a queue and saves all records from that there.

5) I guess we should also right away add service commands for the queue - e.g. get all items, bulk add, get random item. Have a setting flag - with which visibility to include them.

6) for queue manager, there should be the following queue properties:
    - if the queue has 'priority' or not
    - if the queue has 'done' property of some sort - to get items out. for example, for contacts - people should never get out

7) extra idea for queues - copy items from one queue to another etc.
