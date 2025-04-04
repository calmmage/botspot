Sample commit that adds a new component:
"Add telethon_manager component"
cc18f0491d082431a813ac6298b3e899c139379b

The full diff is here: [new_component.txt](../../dev/hide/new_component.txt)

Commit contents:

- new component file
- component added to [config](../core/botspot_settings.py)
- component added to  [depepndency manager](../core/dependency_manager.py)
- setup added to [bot manager](../core/bot_manager.py)
- example added to [components examples](../../examples/components_examples)
- add getter util to [utils](../utils/deps_getters.py) if necessary

Planned structure:
```
botspot/
├── main/
│   ├── single_user_mode.py        # Current: single user checks
│   ├── trial_mode.py              # Current: usage-limited / testing features
│   ├── telethon_manager.py        # Current: Telethon-specific initialization & logic
│   ├── event_scheduler.py         # Current: scheduling system
│   ├── queue_manager.py           # Future: integrated queue structure
│   └── ...
│
├── data/
│   ├── mongo_database.py          # Current: Mongo interactions
│   ├── user_data.py               # Current: user-specific data models
│   ├── people_crm.py             # Future: CRM-like contacts / user details
│   └── ...
│
├── features/
│   ├── ask_user_handler.py        # Current: direct user interactions
│   ├── multi_forward_handler.py   # Current: multi-forward logic
│   ├── command_utils.py           # Future: command-based utilities
│   ├── whisper_audio.py           # Future: audio-parsing integration
│   ├── gpt_handler.py             # Future: GPT chat functionality
│   ├── analytics.py               # Future: analytics / statistics
│   ├── multi_message_processor.py # Future: combine multiple messages
│   └── ...
│
├── middlewares/
│   ├── error_handler.py           # Current: captures and handles errors
│   └── ...
│
├── settings/
│   ├── bot_commands_menu.py       # Current: bot menu system
│   ├── bot_info.py                # Current: minimal info about the bot
│   ├── settings_miniapp.py        # Future: settings interface or specialized config
│   └── ...
│
└── utils/
    ├── print_bot_url.py           # Current: simple utility
    ├── readme.md                  # Current: top-level readme for partial docs
```