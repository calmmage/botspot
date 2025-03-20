## General new improvement ideas

- [ ] move deps_getters to each component and re-import them back to deps_getters from
  there.
- [ ] add a new test that would run only locally and that would just make sure that
  botspot launches fine with the default env settings end-to-end - without mocks.
  something like 'only run if actual telegram token is present in env'

Wishlist

- [ ] cookbok.
- [ ] make a list of
    - small demo bots I want to do with bostpot features
    - big real bots I want to have

Small demo bots:

- a - grok gpt chat bot
    - showcase tech: grok api
    - showcase tech: trial mode / subscription
    - showcase tech: gpt chat with history on timeout / schedule
- b - multi-message chat bot.
- c - chat with my telegram history. Find messages.
- d - simple daily bot
    - post 1 item per day to a telegram channel
    - showcase tech: scheduler component
    - showcase tech: queue component
    - bonus: also post to Twitter
    - bonus: companion bot to get a random item on demand

Big real bots

- whisper bot
- formatter bot
- pictureposter bot (uses feature from ef bot)
- archivist (auto-archive, bind, queue).
- re-feeder bot
- people bot (feature: contact management, queue ingest/parsing, pick a random person)
- oibot (queue, scheduler - assist with task tracking)
- combiner
- chat feed extractor.

The main idea is that basic versions of those bots should be EXTREMELY SIMPLE -

- because of using the botspot components.
  So, this means two things:
- first implementation should rely on botspot features as much as possible
- Botspot components should be developed to the point that key features work out of the
  box and bot implementation on top of them is trivial