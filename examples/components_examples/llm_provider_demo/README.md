# LLM Provider Demo Bot

This example demonstrates how to use the LLM Provider component in Botspot to integrate
Large Language Models (LLMs) like Claude, GPT-4, and others into your Telegram bot.

## Features

This demo showcases:

1. Basic text generation with the LLM Provider
2. Structured output with Pydantic models
3. Streaming responses
4. Integration with Telegram bot commands

## Setup

1. Copy `sample.env` to `.env` and fill in your:
    - Telegram Bot Token
    - Developer Chat ID for error logging
    - API keys for your preferred LLM providers (OpenAI, Anthropic, etc.)

2. Install required dependencies:
   ```bash
   pip install -r ../../requirements.txt
   # Add litellm specifically if not already installed
   pip install litellm
   ```

3. Run the bot:
   ```bash
   python bot.py
   ```

## Available Commands

- `/start` - Display welcome message and command list
- `/ask <question>` - Ask any question to the LLM
- `/analyze_name <name>` - Get a structured analysis of a name
- `/stream <prompt>` - See the LLM response appear word by word

## LLM Provider Features

The LLM Provider component supports:

- Multiple LLM backends via litellm
- Simplified model name shortcuts (e.g., "claude-3.7" instead of "
  anthropic/claude-3-5-sonnet-20240620")
- Asynchronous operation
- Streaming responses
- Structured output with Pydantic models
- Convenient global utility functions

## Example Usage

```python
# Simple text completion
from botspot.components.new import llm_provider

# Quick usage with convenience function
response = await llm_provider.aquery_llm(
    prompt="What is the capital of France?",
    system_message="You are a geography expert.",
)

# Using the provider directly
provider = llm_provider.get_llm_provider()
response = await provider.aquery_llm_text(
    prompt="What are the three branches of government?",
    model="gpt-4o",  # Using a shortcut name
    temperature=0.2
)
```