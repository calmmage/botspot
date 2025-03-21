# Chat Binder

- **Main Feature**: Binds a chat to a user (with an optional key).
- **Demo Bot**: Send `/bind [key]` in a chat; it links the chat to you and echoes "Bound with [key]".
- **Useful Bot**: **Collection Bot** - Binds a chat to a collection, auto-loads messages to a queue, and processes them (e.g., stores or analyzes).

## Developer Notes

Chat binder is already implemented, just need to test that. Next step - integrations.

1) there is a nuance here. This is a very simple but powerful feature. I need to first figure out all the details and work it throgh - create a solid usage examples - and then add documentation everywhere and include it in all my templates. Here are usages I want to have for that feature:

2) bind chat for auto-archiving messages

3) bind chat for all items to be added to a queue - this is our bound_llm_chat component. We can actually make it work without llms - with plain text

4) bind chat for 146 logging. or let's say for dev messages. This is actually should be admin-only feature. And something like that we can have botspot setting, which then, if none, can be specified in runtime by binding... a hidden admin-only command /bind_setting? which would write directly to app.settings or something?

5) what else? What features did I have in mind for this? somehow bind + ingest? I guess that's for /bind_queue component. But yeah, in general, the main idea is to have an easy way to bind a chat and then use that in my app

6) the bot needs admin rights in a bound chat to see all messages - detect and request that.

7) alternatively - use telethon client under the hood.

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