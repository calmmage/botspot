# Queue Manager

- **Main Feature**: Stores items in a MongoDB collection with a uniform internal interface for integrations.
- **Demo Bot**: Send any message; it's auto-added to the queue. Reply with "next" to pull the next item.
- **Useful Bot**: **Task Queue Bot** - Auto-queues messages or tasks, processes them in order or randomly, and integrates with other components (e.g., LLM parsing).

## Developer Notes

1) there is already an implementation - will do a second iteration now

2) there's a clear issue - too much garbage fields + no integration with pydantic, fix that

3) final desired interface is something like get_queue() and add_queue(). with no parameters they should still work - assuming trivial pydantic item type - just a single str field - and default queue key.

4) the basic implementation would be something like a simple bot which you do /bind and it binds chat to a queue and saves all records from that there.

5) I guess we should also right away add service commands for the queue - e.g. get all items, bulk add, get random item. Have a setting flag - with which visibility to include them.

6) for queue manager, there should be the following queue properties:
   - if the queue has 'priority' or not
   - if the queue has 'done' property of some sort - to get items out. for example, for contacts - people should never get out

7) extra idea for queues - copy items from one queue to another etc.

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