# Basic features - first version

1) let's add database to main components. Ok, mongo.
2) add fastapi and frontend to ideas. nextjs for frontend.
3) rewrite @bot.py

- start handler sends you the main menu (inline keyboard)
- main menu is a collection of feature buttons
- settings menu - synced with Settings pydantic model (button for settings)
  let's for now only support on/off bool flags in settings and have 2-3 placeholder
  flags

add more feature Routers and buttons for them in main menu:
a) onboarding (register user in the bot)
b) get info (dummy info inside for now - 3 buttons with placeholder contents)
c) database router

- показать одноклассников
- показать людей в моем городе