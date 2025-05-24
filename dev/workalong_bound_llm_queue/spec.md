# Bound LLM Queue

- **Main Feature**: A queue that auto-parses messages with LLM Utils and requests missing fields, triggered by a single bind action.
- **Demo Bot**: Send `/bind` in a chat; every message after is auto-queued, parsed by LLM (e.g., into a contact form), and prompts for missing fields if needed.
- **Useful Bot**: **People Bot (Enhanced)** - Bind it to a chat; it auto-parses all messages (or forwarded ones) into contacts, stores them, and asks for missing details—all hands-off after `/bind`.

## Developer Notes

For llm queue - first of all, this is a combination of other components - bind, llm utils and queue. But on top of that - also new features enabled by that.

1) ingest -> load all past messages (via telethon client), process them with llm and add to queue. Then some of those messages would have missing mandatory fields -> and we will have procedures to fix that.

2) procedure 1 - /fix_records (or some other name - invent better) command to initiate a process to go through records one by one and fill missing data.

3) procedure 2 - scheduled auto-reminders to ask user about one unfilled item.

4) One more thing - part of these mechanics already implemented in oibot - /Users/petrlavrov/work/projects/outstanding-items-bot
