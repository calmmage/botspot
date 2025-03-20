# Queue Manager Demo

This is a simple demo bot showcasing the Queue Manager component from Botspot.

## Features

- Auto-adds any message to the queue
- Use `/next` to get the next item from the queue
- Use `/random` to get a random item from the queue
- Use `/stats` to see queue statistics
- Use `/clear` to clear the queue

## Requirements

- Python 3.7+
- MongoDB
- Telegram Bot Token

## Setup

1. Copy `sample.env` to `.env`
2. Fill in your Telegram bot token and MongoDB connection details
3. Run `python bot.py`

## Usage

1. Start the bot
2. Send any message to add it to the queue
3. Use the commands to interact with the queue