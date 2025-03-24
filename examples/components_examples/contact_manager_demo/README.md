# Contact Manager Demo

This example demonstrates how to use the Contact Manager component to create a simple contact management bot.

## Features

- Add contacts with a basic schema (name, phone, email, telegram, birthday)
- Auto-parse contact information from regular messages using LLM
- Search contacts by name, email, phone, or other fields
- Get random contacts from your saved list

## Setup

1. Copy `sample.env` to `.env` and update with your settings:
   ```bash
   cp sample.env .env
   ```

2. Edit `.env` file to add your Telegram bot token and other settings

3. Make sure MongoDB is running (required for this component)

4. Install dependencies:
   ```bash
   poetry install
   ```

5. Run the bot:
   ```bash
   python bot.py
   ```

## Usage

- `/add_contact [contact info]` - Add a new contact
  Example: `/add_contact John Doe, phone: 555-1234, email: john@example.com`

- `/find_contact [search term]` - Find contacts matching search term
  Example: `/find_contact John`

- `/random_contact` - Get a random contact from your saved list

- The bot will also automatically detect potential contact information in regular messages and offer to save it.

## Behind the Scenes

This demo uses:
- **MongoDB** for storing contacts
- **LLM Provider** for parsing contact details from text
- **User Data** for managing user access
- **Bot Commands Menu** for registering commands

The Contact Manager component is designed to be extensible for more advanced CRM-like functionality in the future.