# Context Builder

- **Main Feature**: Collects multiple messages forwarded together (bundled with a 0.5s timer), always automatic—no command required.
- **Demo Bot**: Forward any messages to the bot; it waits 0.5s, bundles them, and echoes the combined text as one response.
- **Useful Bot**: **Forwarder Bot** - Auto-bundles forwarded messages, processes them as a unit (e.g., summarizes or stores), and leverages the bundle for context-aware actions.

## Developer Notes

For context builder, there's also a reference implementation - /Users/petrlavrov/work/archive/forwarder-bot i think i actually copied the draft over somewhere to dev/ here as well.

2) another thought is interfaces. I feel like this will be very important here. So let me try to describe what I want:
- there should be a middleware that constructs context and puts it into message metadata
- or how it's usually done in aiogram. there's a canonical way to augment message records with metadata / data - find it and use it.
- the context_builder should have a method build_context(message) which is configurable by settings which describes whether to include in the final context things like reply, forward, transcription of audio etc.
- How to include media.
- A demo bot could be like get multiple messages with images -> construct a blog post somewhere - for example notion or something more straightforward with api.
