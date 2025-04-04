# Botspot Components Example List

This is a list of all components where we should add `__name__ == "__main__"` examples for quick reference.

## Utils Components
- [x] botspot/utils/send_safe.py
- [x] botspot/utils/text_utils.py
- [ ] botspot/utils/cache_utils.py
- [ ] botspot/utils/unsorted.py
- [ ] botspot/utils/admin_filter.py
- [ ] botspot/utils/user_ops.py
- [ ] botspot/utils/deps_getters.py
- [ ] botspot/utils/internal.py

## QOL Components
- [ ] botspot/components/qol/print_bot_url.py
- [x] botspot/components/qol/bot_info.py
- [x] botspot/components/qol/bot_commands_menu.py

## Data Components
- [ ] botspot/components/data/contact_data.py
- [x] botspot/components/data/mongo_database.py
- [x] botspot/components/data/user_data.py

## Features Components
- [ ] botspot/components/features/multi_forward_handler.py
- [ ] botspot/components/features/user_interactions.py

## Main Components
- [x] botspot/components/main/single_user_mode.py
- [ ] botspot/components/main/trial_mode.py
- [ ] botspot/components/main/event_scheduler.py
- [ ] botspot/components/main/telethon_manager.py

## Middleware Components
- [ ] botspot/components/middlewares/error_handler.py

## New Components
- [ ] botspot/components/new/context_builder.py
- [ ] botspot/components/new/contact_manager.py
- [ ] botspot/components/new/subscription_manager.py
- [x] botspot/components/new/llm_provider.py
- [x] botspot/components/new/queue_manager.py
- [ ] botspot/components/new/auto_archive.py
- [x] botspot/components/new/chat_binder.py
- [x] botspot/components/new/chat_fetcher.py

## Core Components
- [ ] botspot/core/errors.py
- [ ] botspot/core/botspot_settings.py
- [ ] botspot/core/bot_manager.py
- [ ] botspot/core/dependency_manager.py