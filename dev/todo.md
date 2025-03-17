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

- Main features (1-2):
  - [ ] Media processing for LLM analysis (screenshots, photos from aiogram)
  - [ ] Smart questionnaire with Pydantic models (fill form, re-ask missing fields)

- Secondary features:
  - [ ] Uniform parser for chat messages (integrate with chat_fetcher and queue)
  - [ ] "Is this good?" validator utility (names, text with guidelines)
  - [ ] Multi-user chat mode for group conversations
  - [ ] Self-aware command assistant (with command registry integration)

Notes:

- Will build on top of the LLM Provider component
- Reference 146 registry bot for media processing
- Will need integration with chat_binder and queue components
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

