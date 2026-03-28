# Botspot

A modern, component-based Telegram bot framework for Python that makes building sophisticated bots simple and maintainable.

## Why Botspot?

- **🧩 Component Architecture**: Modular design with reusable components
- **🔧 Batteries Included**: Database, LLM, storage, and scheduling components
- **⚡ Async First**: Built on aiogram with full async support
- **🛡️ Production Ready**: Error handling, monitoring, and trial modes
- **📱 User-Friendly**: Simplified user interactions and menu systems

## Quick Start

```python
from botspot import Bot
from botspot.components.new import LLMProvider

# Create a bot with LLM capabilities
bot = Bot(token="your_bot_token")
llm = LLMProvider(provider="openai", api_key="your_key")

@bot.message()
async def chat_handler(message, llm: LLMProvider):
    response = await llm.complete(message.text)
    await message.reply(response)

bot.run()
```

## Core Features

### 🧩 **Component System**
Mix and match components to build your bot:
- **Data**: MongoDB, user data, contact management
- **Features**: User interactions, multi-forwarding
- **Main**: Telethon integration, scheduling, trial modes
- **QoL**: Command menus, bot info, URL generation

### 🤖 **AI Integration**
Built-in LLM support:
- OpenAI, Anthropic, and other providers
- Conversation context management
- Streaming responses
- Token usage tracking

### 📚 **Rich Middleware**
- Error handling and logging
- User caching and state management
- Admin filters and permissions
- Trial mode limitations

## Architecture

```
┌─────────────────┐
│   Your Bot      │
├─────────────────┤
│  Components     │  ← Mix & match functionality
├─────────────────┤
│  Botspot Core   │  ← Framework foundation  
├─────────────────┤
│   aiogram       │  ← Telegram API
└─────────────────┘
```

## Get Started

Install with pip or uv:

```bash
uv add botspot
```

Check out the [examples](https://github.com/calmmage/botspot/tree/main/examples) and the [botspot-template](https://github.com/calmmage/botspot-template) to get started.