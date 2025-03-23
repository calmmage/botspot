# Contact Manager (for People Bot)

- **Main Feature**: Manages user contacts with a basic schema (name, phone, email, telegram, birthday) stored in MongoDB.
- **Demo Bot**: Send a message (e.g., "Jane, 555-5678"); it auto-parses and saves as a contact, asking for missing fields if needed.
- **Useful Bot**: **People Bot** - Auto-ingests contacts from chat messages, parses with LLM, stores them, and lets you retrieve random contacts.

## Developer Notes

0) need to decide whether to implement contact manager on top of queue manager or as a completely separate

1) for contacts - people should never get out of the queue

2) AI loves to invent features here. Forbid it. Make sure it is minimal possible implementation to start with - and then extend that

3) need some way to easily ingest contacts: from telegram, from iphone, from gmail, from my old notion / remnote / obsidian.

4) I guess we do this on top of queue manager. Just need data model. The question is how will we add fields later?

5) how to make this extensible into a full-fledged crm?

6) bring over features to send messages to people - from ef random coffee bot. /Users/petrlavrov/work/experiments/ef-community-bot-rc-notifier
