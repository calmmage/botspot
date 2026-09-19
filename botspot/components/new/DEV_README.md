# DEV_README

## Location plans

chat_binder.py -> components/features/chat_binder.py

subscription_manager stays in `components/new/` (package). Public re-export:
`botspot/subscription_manager.py`. Enable with `BOTSPOT_SUBSCRIPTION_MANAGER_ENABLED`
and MongoDB. Friends/admins bypass via `is_friend` / `is_admin`.

Per-user daily trial caps (0 = off):
`BOTSPOT_SUBSCRIPTION_MANAGER_TRIAL_USER_AUDIO_MINUTES_PER_DAY`,
`BOTSPOT_SUBSCRIPTION_MANAGER_TRIAL_USER_AUDIO_REQUESTS_PER_DAY`,
`BOTSPOT_SUBSCRIPTION_MANAGER_TRIAL_USER_CHAT_REQUESTS_PER_DAY`.
`BOTSPOT_SUBSCRIPTION_MANAGER_TRIAL_DURATION_DAYS=0` means no expiry. 