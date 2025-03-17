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
  - [ ] Extract and parse audio
  - [ ] Collect photos/images from messages
  - [ ] Save to database

## Chat Binder
- Main features (1-2):
  - [ ] Bind a chat to a user (with optional key)

- Secondary features:
  - [ ] Integration with Queue component (bind chat to queue)
  - [ ] Auto-load messages to queue

## Queue Manager
- Main features (1-2):
  - [ ] Managing message queues for processing

- Secondary features:
  - [ ] Reuse code from 146_registry_bot for exporting to Sheets
  - [ ] Stats and analytics

## Contact Manager
- Main features (1-2):
  - [ ] Manage user contacts

- Secondary features:
  - [ ] Integrate with queue/llm/bind features
  - [ ] Populate contacts from chat
  - [ ] Chat for contact ingestion

Notes:
- Look up existing draft

## Subscription Manager
- Main features (1-2):
  - [ ] Manage user subscriptions

- Secondary features:
  - [ ] Payment processing

Notes:
- Reuse code from 146_registry_bot for payment processing