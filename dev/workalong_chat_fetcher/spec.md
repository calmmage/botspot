# Chat Fetcher

- **Main Feature**: Fetches Telegram chat messages with caching in MongoDB to avoid re-downloading the same messages.
- **Demo Bot**: `/ingest [chat_id]` - Loads messages from the specified chat into MongoDB (skipping already-cached ones), then `/stats` instantly returns message count and last message from the cache.
- **Useful Bot**: **Chat Analyzer** - Ingests a chat once with `/ingest`, caches it, and provides instant stats (e.g., active users, message frequency) or summaries via LLM, all from the cached data.

**Notes**: The "name of the game is caching"—so `/ingest` checks MongoDB first, only fetching new messages (e.g., by comparing timestamps or message IDs). Subsequent operations like stats pull directly from the cache for speed.

## Developer Notes

0) this is painful. or not. I already have several drafts at it

1) not sure how to start - i can simply implement this standalone as simple feature on top of telethon. or i can use my lib telegram-downloader - beacuse i already did a lot of work there, including caching. For small bot would be better to start small, feel that I can do it. On the other hand. i need to fix and use telegram-downloader. There is no way around using cache, so I will need to do that, and I don't want to do it a second time - why would I?

2) main features - get_chat_messages, get_chats, find_chat, find_messages - and corresponding telegram command handlers (setup visibility through settings)

3) this should be on top of telethon manager - get client from it and pass all relevant arguments

4) link of telegram downloader: /Users/petrlavrov/work/projects/telegram-downloader
IMPORT AND USE IT FOR ALL FEATURES!!!