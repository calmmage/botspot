
What is the plan?

Idea 1: just make a bot and run it

- Done! [basic_bot](../examples/basic_bot)

idea 2: add 'register post link on startup' util
idea 3: try teletalk + new-bot-lib
idea 4: commit
Idea 5: Chat Fetcher - Adapt from existing telegram_downloader implementation

## Task: Integrate telegram-downloader into chat_fetcher component

- Use telegram-downloader from GitHub as dependency (added to pyproject.toml)
- Adapt the chat_fetcher.py to use telegram-downloader features
- Ensure compatibility with MongoDB caching and Telethon client
- Update the component to leverage advanced features from telegram-downloader

