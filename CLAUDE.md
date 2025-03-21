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