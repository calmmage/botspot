# LLM Utils

- **Main Feature**: `parse_input_into_form` - Parses input into a structured form (Pydantic/JSON), allows missing optional fields, and re-asks for missing mandatory fields.
- **Demo Bot**: Send any message (e.g., "John, 555-1234"), it auto-parses to a form (name, phone) and prompts for missing fields (e.g., "What's John's email?").
- **Useful Bot**: **Smart Form Filler** - Auto-parses chat input into forms, queues incomplete ones, and pings the user for missing details over time.

## Developer Notes

1) this is actually hard. Currently, LLM did a first pass, but next steps must be done by user. If you get this task - ask the user to draft proper solutions in a notebook first.

2) need to resolve (litellm/chainlit <-> pydantic <-> structured output issue) optional vs mandatory fields. Currently crashes with missing fields error

3) "Is this a good that" - need to ask the dev. LLM doesn't get it.

4) parse data into form - this actually probably should be a separate component like 'form filler'. Right now this is kind-of just a structured output thing. But let's still have it - as a simple limited version that just spits out well-formatted stuff with smart handling of mandatory/optional fields - with an extra 'missing' flag and proper prompt template

5) auto-parse to queue -> this is a separate component now

6) Whispeer things - take from whisper bot. + utils 'parse audio' - key idea is that I want to be able to pass message.audio or message.voice and have it handled. Reference examples in /Users/petrlavrov/work/archive/whisper-bot

7) same thing for photos and pdfs/files - just pass them to query_llm and have it handled - downloaded, attached, used. Reference examples in /Users/petrlavrov/work/experiments/register-146-meetup-2025-bot
