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

# Botspot Development Guide

## Build & Test Commands
- Install dependencies: `poetry install`
- Run tests: `poetry run pytest`
- Run single test: `poetry run pytest tests/path_to_test.py::test_function_name -v`
- Format code: `poetry run black .`
- Sort imports: `poetry run isort .`
- Lint code: `poetry run flake8`

## Code Style Guidelines
- **Imports**: Use isort with black profile; line length 100
- **Formatting**: Black with 100 character line length
- **Types**: Use type hints and Pydantic for data models
- **Naming**: snake_case for variables/functions, PascalCase for classes, UPPER_CASE for constants
- **Error Handling**: Use try/except with specific exceptions; logging with loguru
- **Component Usage**: Access components via `deps` object or dedicated getters
- **Documentation**: Docstrings for classes and functions in flake8-docstrings format
- **Dependencies**: Managed with Poetry in pyproject.toml

## Adding New Components
When adding a new component, include:
1. New component file in appropriate subdirectory (main/data/features/middlewares/qol)
2. Add component to config in `core/botspot_settings.py`
3. Add component to `core/dependency_manager.py`
4. Setup component in `core/bot_manager.py`
5. Add getter util to `utils/deps_getters.py` if necessary
6. Create example in `examples/components_examples`

The codebase is a Telegram bot framework with modular components. Prefer composition over inheritance when extending functionality.