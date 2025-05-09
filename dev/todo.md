# todo_new_components

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

# Todos from 24 Mar

- [ ] Update all examples to a new template (import base bot)
- [ ] update mini-botspot template and botspot template to new format (using base bot)

Chat binder:
- [x] /bind_status - know if this chat is bound and with which keys 
- [x] /unbind -> check if there are records in the db with this key first. If not - error instead of success
- [x] /unbind -> if default key, check if there are records in db for this chat with any key - and delete that if there's no default

# Todos from 17 Mar

## General new improvement ideas

- [ ] move deps_getters to each component and re-import them back to deps_getters from
  there.
- [ ] add a new test that would run only locally and that would just make sure that
  botspot launches fine with the default env settings end-to-end - without mocks.
  something like 'only run if actual telegram token is present in env'

Wishlist

- [ ] cookbok.
- [ ] make a list of
    - small demo bots I want to do with bostpot features
    - big real bots I want to have

Small demo bots:

- a - grok gpt chat bot
    - showcase tech: grok api
    - showcase tech: trial mode / subscription
    - showcase tech: gpt chat with history on timeout / schedule
- b - multi-message chat bot.
- c - chat with my telegram history. Find messages.
- d - simple daily bot
    - post 1 item per day to a telegram channel
    - showcase tech: scheduler component
    - showcase tech: queue component
    - bonus: also post to Twitter
    - bonus: companion bot to get a random item on demand

Big real bots

- whisper bot
- formatter bot
- pictureposter bot (uses feature from ef bot)
- archivist (auto-archive, bind, queue).
- re-feeder bot
- people bot (feature: contact management, queue ingest/parsing, pick a random person)
- oibot (queue, scheduler - assist with task tracking)
- combiner
- chat feed extractor.

The main idea is that basic versions of those bots should be EXTREMELY SIMPLE -

- because of using the botspot components.
  So, this means two things:
- first implementation should rely on botspot features as much as possible
- Botspot components should be developed to the point that key features work out of the
  box and bot implementation on top of them is trivial

# Todos from 16 Mar

## General

- [ ] tests - ask claude code to add them.
- [ ] cookbook - collect basic bot examples
- [ ] botspot 101 examples

## For each component

- Add component
  - [ ] setup dispatcher
  - [ ] settings
  - [ ] add to deps
  - [ ] initialize

- Add necessary fluff
  - [ ] utils
  - [ ] top level import
  - [ ] tests
  - [ ] examples

## Components:

## LLM Provider - ✅ DONE

- Main features (1-2):
  - [x] Basic query_llm function (prompt -> text response)
  - [x] Async version (aquery_llm)

- Secondary features:
  - [x] Use litellm as backend
  - [x] Support for prompt, system, model parameters
  - [x] Model name shortcuts (e.g., claude-3.7 -> proper litellm keys)
  - [x] Support important models: gpt4o, gpt4.5, grok3, gemini2, etc.

## LLM Utils

Idea:

- Main features (1-2):
  - util to attach telegram photo to llm (just add to query_llm as kwarg?)
  - is_this_a_good_that(input_str, desired_thing, optional: criteria/guidelines) ->
    Response(bool flag,
    that, optional: reason)
  - parse_input_into_form, allow missing optional fields (pydantic / json)
    -> how do i do an integration with queue / bind to auto-parse items + request
    missing fields from user. Should this be a new component, like LLM-parsed bound
    queue?
  -

- Secondary features:
  - 
  - [ ] Uniform parser for chat messages (integrate with chat_fetcher and queue)
  - [ ] "Is this good?" validator utility (names, text with guidelines)
  - [ ] Multi-user chat mode for group conversations
  - [ ] Self-aware command assistant (with command registry integration)
  - [ ] Media processing for LLM analysis (screenshots, photos from aiogram). How do i
    easily attach photo / doc to an llm call?
  - [ ] Smart questionnaire with Pydantic models (fill form, re-ask missing fields)

Notes:

- Will build on top of the LLM Provider component
- Reference 146 registry bot for media processing
- [for questionairre] Will need integration with chat_binder and queue components - to
  really
- Smart form parser should handle various user input styles
- Command registry could be a part of commands_menu
- Dynamic commands example exists in dynamic_commands_bot

## Context Builder

- Main features (1-2):
  - [ ] Collect multiple messages forwarded together (bundle with timer)

- Secondary features:
  - [ ] Support replying to a message with a /command to reference it
  - [ ] Support forwarding a message with a new /command
  - [ ] Extract and parse audio (transcribe to text)
  - [ ] Collect photos/images from messages
  - [ ] Save to database

Notes:

- Old feature was in forwarder_bot
- When new message arrives, start short timer (0.5s)
- Bundle messages forwarded together
- Process all messages together

## Chat Binder

- Main features (1-2):
  - [ ] Bind a chat to a user (with optional key)

- Secondary features:
  - [ ] Integration with Queue component (bind chat to queue)
  - [ ] Auto-load messages to queue

Notes:

- Already implemented mostly
- Need to add integrations with other components

## Queue Manager

- Main features (1-2):
  - [ ] Managing message queues for processing

- Secondary features:
  - [ ] Export data to external sources
  - [ ] Stats and analytics

Notes:

- Reuse code from 146_registry_bot for exporting to Sheets
- Consider adding stats/analytics features

## Auto Archive

- Main features (1-2):
  - [ ] Auto-archive old conversations/data

Notes:

- Basic structure created in new components folder

## Contact Manager

- Main features (1-2):
  - [ ] Manage user contacts
  - [ ] Basic person schema (name, phone, email, telegram, birthday)
  - [ ] Store person data in MongoDB

- Secondary features:
  - [ ] Integrate with queue/llm/bind features
  - [ ] Populate contacts from chat
  - [ ] Chat for contact ingestion
  - [ ] Add/update/get/list person data
  - [ ] Parse text input with LLM to extract person data
  - [ ] Import from different sources (telegram contacts, google, apple)
  - [ ] Deduplication/merging of contacts

Notes:

- Look up existing draft
- Explored people-bot with core schema: name, phone, email, telegram, birthday
- Options for implementation:
  1. Use queue component as base (collection_prefix approach)
  2. Create separate collection/component (more specialized features)
  3. Consider parsing text with LLM to extract contact details
- Both options have pros: queue offers synergies for import/parse, separate gives more
  flexibility
- Existing work in experiments/people-bot has basic structure but minimal implementation
- Integrate with other components (queue/llm/bind)
- Should have chat to send contacts for ingestion

## Subscription Manager

- Main features (1-2):
  - [ ] Manage user subscriptions

- Secondary features:
  - [ ] Payment processing

Notes:

- Reuse code from 146_registry_bot for payment processing

# Todos from 26 Jan

- [ ] Add support for @username in all user lists (BOTSPOT_FRIENDS, BOTSPOT_ADMINS and
  possible others)

# Todos from 25 Jan

- [ ] Add new global setting 'dev_ids' for developer telegram ids. Automatically include them in admins.
- [ ] convert "send_error_messages" component setting to flag and use dev ids by default

# Todos from 19 Jan

- [ ] Refactor botspot components - split into submodules
- [ ] Track used components and auto-enable them on import? Or warn about missing
  components / guide through how to enable them (in particular - necessary env fields)
- [ ] implement component dependency and initialization order?

- [x] Convert all the api keys in configs to secret_str

# Todos from 06 Jan

- [ ] Add timezone scheduling code from simple cat feeding reminder bot

# Todos from 04 Jan

- [ ] add enum support for
- [ ] find example of timezone handling
    - [ ] add timezone handling to scheduler component

- [x] add user data support
  - [x] add mongodb support - with motor
    - [ ] add data models


- [ ] add mongo example
  - [ ] user db
  - [ ] store messages
  - [ ] store and recover event schedule
- [ ] auto-register users with middleware
  - [ ] alternative: just start command

- [ ] better start command: some kind of super() mechanic to avoid disabling key
  functionality. Or just middleware? - with filter on start
- [ ] better help command. Show all available commands (even not in main menu)

# Todos from 27 Dec

- [x] rework of notify_on_timeout and default_choice in ask_user component

Systems that I have
- BotManager
- Deps
- BotSettings
- utils (have access to deps, not registered)
- components

# Todos

## TDD-like Example Development
- [ ] Create a new folder `dev/examples`
- [ ] Develop example scenarios:
  - [ ] Basic bot setup
  - [ ] Error handling
  - [ ] User input handling
  - [ ] Multi-message processing
  - [ ] File handling (upload/download)
  - [ ] Inline keyboard example
  - [ ] Conversation flow example
  - [ ] Plugin integration example
- [ ] For each example:
  - [ ] Write the desired usage code
  - [ ] Identify missing components/utils
  - [ ] Implement necessary components/utils
  - [ ] Refactor and optimize as needed

## Component Development
- [ ] Improve error handling component
- [ ] Develop user input handling utility
- [ ] Create a multi-message processing component
- [ ] Implement file handling utilities
- [ ] Develop a conversation flow manager
- [ ] Create a plugin system for easy extensions

## Utils and Helpers
- [ ] Implement a flexible command parser
- [ ] Create a message formatting utility
- [ ] Develop a config management system
- [ ] Implement logging utilities

## Testing and Documentation
- [ ] Set up unit tests for each component
- [ ] Write integration tests for examples
- [ ] Create comprehensive documentation for each component
- [ ] Develop a quick start guide

## Optimization and Refactoring
- [ ] Review and optimize BotManager
- [ ] Refactor Dependency management system
- [ ] Improve overall project structure

## Extra Features
- [ ] MongoDB integration
- [ ] RocksDB integration
- [ ] User data management system
- [ ] Timezone / Location handling
- [ ] Config system (per user)
- [ ] Admin page (for bot owner)
- [ ] Trial mode implementation

## Future Considerations
- [ ] Explore integration with teletalk
- [ ] Consider implementing a web interface for bot management

Remember to prioritize tasks and tackle them incrementally. Start with the most critical examples and components, then build upon them as you progress.

Extras
- [ ] Try teletalk

