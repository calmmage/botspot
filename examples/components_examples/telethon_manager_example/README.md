# Telethon Manager Example

This example demonstrates how to use the `telethon_manager` component to manage Telegram user clients in your bot.

## Features

- Setup Telegram user clients using Telethon
- Manage multiple user sessions
- Automatic session persistence
- Support for 2FA authentication

## Setup

1. Copy `sample.env` to `.env` and fill in the required values:
   ```env
    # Bot token from @BotFather
   TELEGRAM_BOT_TOKEN=your_bot_token
   # Telethon manager settings
   BOTSPOT_TELETHON_MANAGER_ENABLED=true
   BOTSPOT_TELETHON_MANAGER_SESSIONS_DIR=sessions
   # Telegram API credentials from https://my.telegram.org/apps
   BOTSPOT_TELETHON_MANAGER_API_ID=your_api_id
   BOTSPOT_TELETHON_MANAGER_API_HASH=your_api_hash
   ```

2. Install dependencies:
   ```bash
   pip install botspot telethon
   ```

3. Run the example:
   ```bash
   python main.py
   ```

## Available Commands

- `/setup_telethon` - Setup a new Telethon user client
- `/setup_telethon_force` - Force setup of a new Telethon client (removes existing session)
- `/check_telethon` - Check if you have an active Telethon client

## Usage Flow

1. Start the bot and send `/setup_telethon`
2. Enter your phone number when prompted
3. Enter the verification code sent to your Telegram account
4. If you have 2FA enabled, enter your password
5. Your session will be saved and can be reused in future bot restarts

## Notes

- The component requires the `ask_user` component to be enabled for interactive setup
- Sessions are stored in the `sessions` directory by default
- Each user can have only one active session at a time 