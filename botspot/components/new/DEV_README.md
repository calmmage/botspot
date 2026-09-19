# DEV_README

## Location plans

chat_binder.py -> components/features/chat_binder.py

subscription_manager stays in `components/new/` (package). Public re-export:
`botspot/subscription_manager.py`. Enable with `BOTSPOT_SUBSCRIPTION_MANAGER_ENABLED`
and MongoDB. Friends/admins bypass via `is_friend` / `is_admin`. 