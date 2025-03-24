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
