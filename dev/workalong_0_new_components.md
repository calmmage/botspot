## The task

So, what's the plan?

Idea:

- I am using AI to create new components
- AI misunderstands me and goes over the place, creates wrong stuff.
- So instead I want to create a very specific list of short and verifyable demos of
  components. Demo should be short and clear, showcasing the usefullness of the new
  component

Here's what I want to do:

- a) component - list of our new components
- b) main simple feature that component should enable - for each - one specific main
  feature it's providing
- c) for each - one specific idea of a simple bot showcasing the usage of the main
  feature
- d) for each - an idea of actual useful bot I want to have essentially based on that
  component.

One mini-project for each new component

Here are the new components - main things I want to have asap

- llm provider
- llm utils
- context builder - middleware to put context into state?
    - a) Copy whisper bot
    - b) Copy forwarder bot (-> formatter bot)
    - c) add a new feature to gpt / formatter bot - apply command to a past message
        - d) a new component - botspot commands? Alternative ways to request missing
          input / get text of a reply_to message? e.g. util?
- queue
- contact management
    - save people data
    - parse from chat - history
    - import
    - get random person
    - log interaction (s)
    - monitor in telegram - keep who didn't talk to in a while
- telethon manager
    - get chat messages


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
  -
- [ ] populate this from telegram tech ideas:

## Bot ideas

### ⭐️idea 1

people bot

- add person
- Get a random person
- ingest a list of people from a source [[LLM Utils]]
- mark 'conversation done' with a person

### ⭐️idea 2

LLM parse data for an item and fill together missing

### ⭐️idea 3

/Bind feature - to a chat.
-> for example bind chat to a collection -> then store items from that chat
Or /bind an archive chat
Usage: Archivist bot.

### ⭐️Idea 4

Tech: /Ingest

- go over historical messages
- Process
- -> save them to queue

- --

- Queue processing mechanism? IdeA ...
    - Some fancy random event logic - schedule "triage" for example
- usage examples:
    - Archivist
    - People bot
    - 146 bot

### 🔥Idea 5

- dynamic commands bot
    - tech: LLM parser
    - Tech: LLM user (chat with anything)
    - Tech: schedule.
      Mode 1: personal bot (updates commands)
      Mode 2: public bot. (Doesn't update commands)

### Idea 6

-Tech:  Queue

- mode 1: get a random
- Mode 2: work session. Process multiple items one by one

### Idea 7

- reply to reference
    - Include text of the message as content

### Idea 8

- chat about anything ()
    - a) Make LLM see message history with the bot
    - b) Make LLM aware of bot commands and features
    - c) make LLM able to call bot commands?
    - Or expose some of the internal apis / handles / commands to LLM as well

### Idea 9

- multi message as content
    - Idea: if I forward a few messages and I send a /command as a comment to that
      message
    - Option 1: the command knows to go stored multi-message cache
    - Option 2: multi-message handler knows to pick first message and call a command
        - Will need to make multi-message a middleware?
        - And add filter to all messages / router like "..."

### idea 10

Auto-cleanup
(+ Bind -> archive chat)

- block if archive chat is not set up / prompt setup scenario.

### idea 11

- 146 bot
    - Crm
    - Data parsing scenario (with LLM)

### idea 12

- take 146 data and process it

Multi message.

LLM.

- tech: ... Multi-message support
- Re-feeder

### ⭐️idea 13

Search my messages

- features: search messages sent by ME
- a) load all my messages to db
- b) embeddings search
- c) keyword search (llm-driven)
- d) LLM highlights a few candidates.

### Idea 14

Telegram downloader

- set up a job that runs the downloader daily
- Improve usability a little bit (smartly detect when no new messages and skip logging.)
- util to have quick access in python /
- Remove too secret messages? Naah, there's nothing really..

### idea 15

CalmMage bot

- /stat on chats
- /Stat on messages
  Etc.
  Example
- /daily stats (date)
- Active chats - received, Written to
- Messages received, sent
  -/weekly stats 1 For a week?

Search my messages

### Idea 16

Simple GPT bot

- query GPT
- Auto-reset history after a while
- Reply to reference - idea ..
-
- tech: Trial mode, quota

### idea 17 - CRM Tech

Crm

- simple collection in mongo
- There: Contacts class
- Deafult fields - ...
- Extensible

Features:

- ingest from chat
- Ingest from chat members list
- Ingest from csv
- connectors?
    - Google sheets
    - Ingest from Google / apple contacts

Usage:

### 🔥Idea 18

Chatter bot

- add to a group chat
- Make it so bot naturally participates in a conversation together with everyone. -
  Looks at everyone messages
- References people in the chat, has relationships and history with them.

### 🔥Idea 19

Fancy game - trick LLM to get points from it

### ⭐️Idea 20

OIBot!!! Task Tracker
Features

- queue
- Todoist integration
- Schedule

### Idea 21: fuzzy

Simple queue bot?
Get random item from queue
Bind
Etc.?
This should be replaced by:

- Archivist bot
- Re-feeder bot

### Idea 22

Personal Assistant
Scenario - I just want to tell LLM to do something
Expose commands / internals to the LLM.

### Idea 23 - fuzzy

- personal coder
  Scenario: I am in the bed at night.
  I just want to tell LLM to write some code or write something down for me

### Idea 24 - fuzzy

Productivity? Calendar

- idea 1: in the morning
- idea 2: look at my calendar / put stuff dynamically there - based on current state
- Idea 3: some kind of life load management system

- ---

- Track a) active processes (maybe in multiple categories - for example, projects,
  people, travel, habits / hobbies?)
- Track b) my exhaustion levels

### Idea 25

Archivist bot:

- idea "can write down the thing to the right place"
- Tech: reference forward as content
- feature: associates a chat with a collection and stores stuff there
    - [ ] Tech: bind
    - [ ] Tech: queue
- can fill out missing info
    - Tech: put record to a queue for processing
    - Tech: ask user / clarify with user
    - Tech: command constructor to clarify with user

### idea 26. Llm/tg Util for filling forms

Command constructor that can clarify with user missing details - mandatory and optional

Idea:
Tech: parse with llm -> structured output
Fields have mandatory true/false flags

Then for mandatory fields if they are missing - we require user to provide data for each
one

### Idea 27 - fuzzy. Postpone unfinished processing.

Feature idea: be able to postpone processing / filling out the details about an item /
ingested items

Case 1) I sent message to bot,to save. But LLM decided that fields are missing. It tells
me, but I don't respond.
Then I want it to put it into my "backlog" queue
Then, I should be able

- process items on demand
- Get a scheduled random reminder / notification about that

### idea 28

Tech: "last seen in telegram"
Usage: Idea 24 - productivity day planner
Usage 2: EF challenge - who went to sleep when

# Idea 29

Notification manager

- aggregate notifications from my different sources
- Send with care to my attention

# Idea 30

- personal data feeds
- a) telegram
- b) gmail
- c) calendar
- D) local - obsidian
- e) Bookmarks in chrome
- more data - not really critical
- F) notion
- G) gpt chats

# Idea 31

Realistic GPT bot
bot

- With ...
- Can reply multiple times, with a delay. "Typing" feature
- Respond to the body of messages so far

# idea 32

Some idea from Alex

- in chat
- About message forwarding or something.

# idea 33

Forwarder bot

- tech: chat-about-anything

### idea 34

- I had some ideas about askUser improvements. -> so that they can answer both as text
  and as choice callback.

### idea 35

Telethon utils - make my telethon downloader accessible!!

- calmlib - telethon db
- Botspot - telethon client / maybe db cached
  a) find chat
  b) get messages from chat
  c) get chats -> stats about chats
  d) determining chat type
  e) some more quick reasonable in-depth tools?

### idea 36

Multi-message support

- multi-message as content
- Use case: forwarder bot

### 🔥idea 37

Chat summary bot

- find coolest messages by emojis
- Find coolest messages with llms
- Compile in a comprehensive digest
- Extract conversation threads

---
Feed highlights into a some kind of digest

- for chat owners
- For ... Users -> subscribe.
    - Personalized feed, but you own it
- This is a project with Alex! Idea ..32

### Idea 38

Telegram chat -> knowledge base
a) chat with knowledge
b) detect valuable threads, extract topics and insights
c) structure the knowledge.

### Idea 39

Tech: auto-archive
Uses tech: Bind

Use cases:

- archivist input
- Some other? Personal bot, notifs manager, Andy ingestor / consumer?

### Idea 40

Personal daily digest

Usage: CalmMage bot
Tech 1: take my current state / capacity and adapt the information load for that

Idea 2: get me a random useful item from my life.

- outstanding task
- Email
- unreplied message
- Etc.
- Bookmark to process

## The resulting selection

I hear you—my initial take did dampen the automation vibe you’re going for, and I see
how manual commands like `/ask` or `/add_item` kill the seamless, buzz-worthy experience
you want. Let’s pivot to emphasize the automatic, frictionless behavior you’re
envisioning, especially for components like Bound LLM Queue and Context Builder. I’ll
also tweak the GPT bot to skip unnecessary commands and lean into your existing
implementations. Here’s the revised plan, keeping the spirit alive:

---

### Updated Component List

1. **LLM Provider** ✅
2. **LLM Utils**
3. **Context Builder**
4. **Queue Manager**
5. **Contact Manager (for People Bot)**
6. **Chat Fetcher**
7. **Subscription Manager**
8. **Auto Archive**
9. **Chat Binder**
10. **Bound LLM Queue**

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