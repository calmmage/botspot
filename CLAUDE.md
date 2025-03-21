# LLM Utils

- **Main Feature**: `parse_input_into_form` - Parses input into a structured form (Pydantic/JSON), allows missing optional fields, and re-asks for missing mandatory fields.
- **Demo Bot**: Send any message (e.g., "John, 555-1234"), it auto-parses to a form (name, phone) and prompts for missing fields (e.g., "What's John's email?").
- **Useful Bot**: **Smart Form Filler** - Auto-parses chat input into forms, queues incomplete ones, and pings the user for missing details over time.

## Developer Notes

1) this is actually hard. Currently, LLM did a first pass, but next steps must be done by user. If you get this task - ask the user to draft proper solutions in a notebook first.

2) need to resolve (litellm/chainlit <-> pydantic <-> structured output issue) optional vs mandatory fields. Currently crashes with missing fields error

3) "Is this a good that" - need to ask the dev. LLM doesn't get it.

4) parse data into form - this actually probably should be a separate component like 'form filler'. Right now this is kind-of just a structured output thing. But let's still have it - as a simple limited version that just spits out well-formatted stuff with smart handling of mandatory/optional fields - with an extra 'missing' flag and proper prompt template

5) auto-parse to queue -> this is a separate component now

6) Whispeer things - take from whisper bot. + utils 'parse audio' - key idea is that I want to be able to pass message.audio or message.voice and have it handled. Reference examples in /Users/petrlavrov/work/archive/whisper-bot

7) same thing for photos and pdfs/files - just pass them to query_llm and have it handled - downloaded, attached, used. Reference examples in /Users/petrlavrov/work/experiments/register-146-meetup-2025-bot

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