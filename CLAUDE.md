# Bound LLM Queue

- **Main Feature**: A queue that auto-parses messages with LLM Utils and requests missing fields, triggered by a single bind action.
- **Demo Bot**: Send `/bind` in a chat; every message after is auto-queued, parsed by LLM (e.g., into a contact form), and prompts for missing fields if needed.
- **Useful Bot**: **People Bot (Enhanced)** - Bind it to a chat; it auto-parses all messages (or forwarded ones) into contacts, stores them, and asks for missing details—all hands-off after `/bind`.

## Developer Notes

For llm queue - first of all, this is a combination of other components - bind, llm utils and queue. But on top of that - also new features enabled by that.

1) ingest -> load all past messages (via telethon client), process them with llm and add to queue. Then some of those messages would have missing mandatory fields -> and we will have procedures to fix that.

2) procedure 1 - /fix_records (or some other name - invent better) command to initiate a process to go through records one by one and fill missing data.

3) procedure 2 - scheduled auto-reminders to ask user about one unfilled item.

4) One more thing - part of these mechanics already implemented in oibot - /Users/petrlavrov/work/projects/outstanding-items-bot

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