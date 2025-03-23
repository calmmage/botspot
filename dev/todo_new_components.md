

### Updated Component List

1. **LLM Provider** ✅
2. **LLM Utils**
3. **Context Builder**
4. **Queue Manager** ✅
5. **Contact Manager (for People Bot)**
6. **Chat Fetcher**
7. **Subscription Manager**
8. **Auto Archive**
9. **Chat Binder**
10. **Bound LLM Queue**
11.

- For telethon manager

- Features for sending messages - utils. Send message to contacts, queue members.
  - this is implemented in
- Features for working with reactions
- features for working with polls
  - make sure ... to vote
  - use ef rc notifier aas example

12.

- Settings menu

- for botspot settings
- as mini-app
- as inline buttons - e.g. ask_user_choice (inline keyboard) - maybe use aiogram-dialog

---

### a) Component

### b) Main Feature (Your Exact Specs)

### c) Simple Demo Bot (Minimal, Auto-Driven Showcase)

### d) Idea for Useful Bot (Buzz-Worthy Application)

#### 1. LLM Provider ✅

- **b) Main Feature**: Basic `query_llm` function (prompt -> text response) with async
  support (`aquery_llm`).
- **c) Demo Bot**: Any message sent to the bot is auto-queried to the LLM, and it
  responds with the raw output—no `/ask` needed.
- **d) Useful Bot**: **Simple GPT Bot** - Treats every message as an LLM query, responds
  naturally, resets history after a timeout, and supports model shortcuts.

#### 2. LLM Utils

- **b) Main Feature**: `parse_input_into_form` - Parses input into a structured form (
  Pydantic/JSON), allows missing optional fields, and re-asks for missing mandatory
  fields.
- **c) Demo Bot**: Send any message (e.g., "John, 555-1234"), it auto-parses to a form (
  name, phone) and prompts for missing fields (e.g., "What’s John’s email?").
- **d) Useful Bot**: **Smart Form Filler** - Auto-parses chat input into forms, queues
  incomplete ones, and pings the user for missing details over time.

#### 3. Context Builder

- **b) Main Feature**: Collects multiple messages forwarded together (bundled with a
  0.5s timer), always automatic—no command required.
- **c) Demo Bot**: Forward any messages to the bot; it waits 0.5s, bundles them, and
  echoes the combined text as one response.
- **d) Useful Bot**: **Forwarder Bot** - Auto-bundles forwarded messages, processes them
  as a unit (e.g., summarizes or stores), and leverages the bundle for context-aware
  actions.

#### 4. Queue Manager

- **b) Main Feature**: Stores items in a MongoDB collection with a uniform internal
  interface for integrations.
- **c) Demo Bot**: Send any message; it’s auto-added to the queue. Reply with “next” to
  pull the next item.
- **d) Useful Bot**: **Task Queue Bot** - Auto-queues messages or tasks, processes them
  in order or randomly, and integrates with other components (e.g., LLM parsing).

#### 5. Contact Manager (for People Bot)

- **b) Main Feature**: Manages user contacts with a basic schema (name, phone, email,
  telegram, birthday) stored in MongoDB.
- **c) Demo Bot**: Send a message (e.g., "Jane, 555-5678"); it auto-parses and saves as
  a contact, asking for missing fields if needed.
- **d) Useful Bot**: **People Bot** - Auto-ingests contacts from chat messages, parses
  with LLM, stores them, and lets you retrieve random contacts.

#### 6. Chat Fetcher

- **b) Main Feature**: Fetches Telegram chat messages with caching in MongoDB to avoid
  re-downloading the same messages.
- **c) Demo Bot**: `/ingest [chat_id]` - Loads messages from the specified chat into
  MongoDB (skipping already-cached ones), then `/stats` instantly returns message count
  and last message from the cache.
- **d) Useful Bot**: **Chat Analyzer** - Ingests a chat once with `/ingest`, caches it,
  and provides instant stats (e.g., active users, message frequency) or summaries via
  LLM, all from the cached data.

**Notes**: The “name of the game is caching”—so `/ingest` checks MongoDB first, only
fetching new messages (e.g., by comparing timestamps or message IDs). Subsequent
operations like stats pull directly from the cache for speed.

#### 7. Subscription Manager

- **b) Main Feature**: Manages paid subscriptions—users pay, send screenshots, and
  unlock tiered features/commands.
- **c) Demo Bot**: Send a payment screenshot; bot verifies it (manually or via LLM),
  assigns a tier (e.g., Basic, Pro), and unlocks tier-specific commands like
  `/pro_feature` for Pro users.
- **d) Useful Bot**: **Tiered Bot** - Users subscribe by paying and sending proof; Basic
  tier gets core features (e.g., `/stats`), Pro tier adds advanced ones (e.g.,
  `/analyze` with LLM), all tied to a subscription status in MongoDB.

**Notes**: Ditched my invented feed idea—now it’s all about paid tiers. Verification
could be manual or automated (e.g., LLM checks screenshot text for payment details).
Commands are gated by tier, keeping it simple and profitable.

#### 8. Auto Archive

- **b) Main Feature**: Forwards messages to a bound archive chat and deletes them from
  the original conversation to keep it clean.
- **c) Demo Bot**: Bind it with `/bind_archive [archive_chat_id]`; send any message—it
  auto-forwards to the archive chat and deletes from the original chat.
- **d) Useful Bot**: **Clean Inbox Bot** - Bind it to an archive chat; it forwards all
  messages (or specific ones) there, deletes them from your input chat, and maintains a
  clutter-free space.

**Notes**: The flow is exactly as you described—message in, forward to archive, delete
from convo. Binding sets up the archive chat once, then it’s fully automatic.

#### 9. Chat Binder

- **b) Main Feature**: Binds a chat to a user (with an optional key).
- **c) Demo Bot**: Send `/bind [key]` in a chat; it links the chat to you and echoes
  “Bound with [key]”.
- **d) Useful Bot**: **Collection Bot** - Binds a chat to a collection, auto-loads
  messages to a queue, and processes them (e.g., stores or analyzes).

#### 10. Bound LLM Queue

- **b) Main Feature**: A queue that auto-parses messages with LLM Utils and requests
  missing fields, triggered by a single bind action.
- **c) Demo Bot**: Send `/bind` in a chat; every message after is auto-queued, parsed by
  LLM (e.g., into a contact form), and prompts for missing fields if needed.
- **d) Useful Bot**: **People Bot (Enhanced)** - Bind it to a chat; it auto-parses all
  messages (or forwarded ones) into contacts, stores them, and asks for missing
  details—all hands-off after `/bind`.

- 11 - For telethon manager
  - Features for sending messages - utils. Send message to contacts, queue members.
    - this is implemented in
  - Features for working with reactions
  - features for working with polls
    - make sure ... to vote
    - use ef rc notifier aas example
- 12 - Settings menu
  - for botspot settings
  - as mini-app
  - as inline buttons - e.g. ask_user_choice (inline keyboard) - maybe use
    aiogram-dialog