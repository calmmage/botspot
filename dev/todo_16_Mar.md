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

## LLM Provider
- Main features (1-2):
  - [ ] Basic query_llm function (prompt -> text response)
  - [ ] Async version (aquery_llm)

- Secondary features:
  - [ ] Use litellm as backend
  - [ ] Support for prompt, system, model parameters
  - [ ] Model name shortcuts (e.g., claude-3.7 -> proper litellm keys)
  - [ ] Support important models: gpt4o, gpt4.5, grok3, gemini2, etc.

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
- Both options have pros: queue offers synergies for import/parse, separate gives more flexibility
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