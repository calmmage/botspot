# Settings Menu Demo

This is a demonstration of the Botspot Settings Menu component, which provides a configurable UI for managing bot settings.

## Features

- Admin Settings: Configure botspot components (admin-only)
- User Settings: Customizable per-user preferences
- Inline Keyboard Interface: Easily navigate through setting categories and options

## Usage

1. Install dependencies with Poetry
2. Create a `.env` file using `sample.env` as a template
3. Run the bot: `python bot.py`

## Commands

- `/settings` - Open user settings menu
- `/admin_settings` - Open admin settings menu (admin-only)

## Example Settings

### Admin Settings
- Default LLM Model
- LLM Temperature
- Allow Everyone to Use LLM

### User Settings
- Enable Notifications
- Preferred Language

## Dependencies

- User Data component (for storing user settings)
- Admin Filter (for admin-only settings)