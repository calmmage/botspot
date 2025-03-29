# Context Builder Demo

This example demonstrates the context builder component that bundles multiple messages sent within a short time period into a single context.

## Features

- Automatically bundles messages sent within a 0.5-second window
- Combines text from multiple messages into a single context
- Includes metadata for images and other media
- Demonstrates how to access the bundled context in a message handler

## Usage

1. Clone the repository
2. Create a `.env` file based on `sample.env` and set your Telegram bot token
3. Run the example: `python bot.py`
4. Forward multiple messages to the bot within a short time frame
5. The bot will respond with the combined context

## Configuration

The context builder can be configured via environment variables:

- `BOTSPOT_CONTEXT_BUILDER_ENABLED` - Enable/disable the component (default: false)
- `BOTSPOT_CONTEXT_BUILDER_BUNDLE_TIMEOUT` - Time window in seconds to bundle messages (default: 0.5)
- `BOTSPOT_CONTEXT_BUILDER_INCLUDE_REPLIES` - Include reply messages in context (default: true)
- `BOTSPOT_CONTEXT_BUILDER_INCLUDE_FORWARDS` - Include forwarded messages in context (default: true)
- `BOTSPOT_CONTEXT_BUILDER_INCLUDE_MEDIA` - Include media descriptions in context (default: true)
- `BOTSPOT_CONTEXT_BUILDER_INCLUDE_TEXT` - Include text content in context (default: true)