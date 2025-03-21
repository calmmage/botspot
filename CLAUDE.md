# Context Builder

- **Main Feature**: Collects multiple messages forwarded together (bundled with a 0.5s timer), always automatic—no command required.
- **Demo Bot**: Forward any messages to the bot; it waits 0.5s, bundles them, and echoes the combined text as one response.
- **Useful Bot**: **Forwarder Bot** - Auto-bundles forwarded messages, processes them as a unit (e.g., summarizes or stores), and leverages the bundle for context-aware actions.

## Developer Notes

For context builder, there's also a reference implementation - /Users/petrlavrov/work/archive/forwarder-bot i think i actually copied the draft over somewhere to dev/ here as well.

2) another thought is interfaces. I feel like this will be very important here. So let me try to describe what I want:
- there should be a middleware that constructs context and puts it into message metadata
- or how it's usually done in aiogram. there's a canonical way to augment message records with metadata / data - find it and use it.
- the context_builder should have a method build_context(message) which is configurable by settings which describes whether to include in the final context things like reply, forward, transcription of audio etc.
- How to include media.
- A demo bot could be like get multiple messages with images -> construct a blog post somewhere - for example notion or something more straightforward with api.

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