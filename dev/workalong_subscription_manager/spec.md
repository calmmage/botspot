# Subscription Manager

- **Main Feature**: Manages paid subscriptions—users pay, send screenshots, and unlock tiered features/commands.
- **Demo Bot**: Send a payment screenshot; bot verifies it (manually or via LLM), assigns a tier (e.g., Basic, Pro), and unlocks tier-specific commands like `/pro_feature` for Pro users.
- **Useful Bot**: **Tiered Bot** - Users subscribe by paying and sending proof; Basic tier gets core features (e.g., `/stats`), Pro tier adds advanced ones (e.g., `/analyze` with LLM), all tied to a subscription status in MongoDB.

**Notes**: Verification could be manual or automated (e.g., LLM checks screenshot text for payment details). Commands are gated by tier, keeping it simple and profitable.

## Developer Notes

1) there should be a concept of 'number of tiers' for subscription. default - 1 - just free / subscribed.

2) there should be a concept of free trial - timed.

3) there should be a way to mark a command / feature as available to subscribed members only. for example, a decorator or middleware. Maybe both combined. Middleware will be registered in component dp setup and would check if current user has access to curernt command / feature

4) there should also be a way to limit global message handler (e.g. simple text chat messages) - for example if passing an empty command

5) there should be a payment mechanism. For now - use the same one as done in 146 bot /Users/petrlavrov/work/experiments/register-146-meetup-2025-bot
