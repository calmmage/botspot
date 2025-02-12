# Botspot

A collection of cross-integrated utils and components for Telegram bots.

## Description

Botspot features 3 main sections:
- core
configure and connect the botspot components to your aiogram dispatcher
- components
featured: user_data
- utils
featured: send_safe

## Quick Start

1. Clone template repository https://github.com/calmmage/botspot-template
2. Enable/disable components with example.env
3. Run the bot with run.py
4. You can see component usage examples at https://github.com/calmmage/botspot/tree/main/examples
5. Generally, you can access components via singleton `deps` object and deps_getters utils 
```python
from botspot.utils.deps_getters import get_bot, get_database, get_scheduler
```

