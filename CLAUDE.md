# Settings Menu

- **Main Feature**: Provides a configurable UI for managing bot settings with two modes - admin settings (configure botspot components) and user settings (customizable per-user preferences).
- **Demo Bot**: `/settings` command that displays an inline keyboard or web app with settings options, allowing users to toggle, select, or input different configuration values.
- **Useful Bot**: **Config Bot** - Enables users to personalize their experience via simple settings UI, while admins can adjust system parameters (like LLM provider settings) without editing code files.

## Developer Notes

The idea of a settings menu is two-fold:

1) Idea 1 - have a menu for configuring botspot settings. I guess that can be admin-only. Specifically that is necessary for llm provider - which model to use - etc. Well, for single-user mode that will be for admins.

2) Idea 2 - user settings. I guess that can be integrated with UserManager and having custom fields for configuration in User class. But need to figure out how to deal with booleans, enums and all that stuff.

3) Then - form factor.
   - Option 1 - web app / mini-app.
   - Option 2 - inline keyboard. I haven't done either yet. Well, i've done inline keyboard, but i think maybe i will need aiogram-dialogue for that. But I've also heard it's better to just do it myself properly. So need to try and see how this will work.

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