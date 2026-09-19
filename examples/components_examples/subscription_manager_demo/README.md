# subscription_manager demo

Enable MongoDB and `BOTSPOT_SUBSCRIPTION_MANAGER_ENABLED=true`. Friends and admins
bypass billing (`BOTSPOT_FRIENDS_STR` / `BOTSPOT_ADMINS_STR`).

Commands registered by the component: `/subscribe`, `/plans`, `/account`, `/buy`,
admin `/grant`, `/revoke`, `/subscribers`, `/grant_credits`.

Per-user daily trial caps (0 = off):
`BOTSPOT_SUBSCRIPTION_MANAGER_TRIAL_USER_AUDIO_MINUTES_PER_DAY`,
`BOTSPOT_SUBSCRIPTION_MANAGER_TRIAL_USER_AUDIO_REQUESTS_PER_DAY`,
`BOTSPOT_SUBSCRIPTION_MANAGER_TRIAL_USER_CHAT_REQUESTS_PER_DAY`.
`BOTSPOT_SUBSCRIPTION_MANAGER_TRIAL_DURATION_DAYS=0` means no expiry (public free
tier). Hitting a daily cap returns `Decision.reason=trial_daily_cap`.
