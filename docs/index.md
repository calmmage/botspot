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

1. **[Installation & Setup](getting-started.md)** - Get your first bot running
2. **[Components Guide](components/index.md)** - Learn the component system
3. **[Examples](examples.md)** - See real-world implementations
4. **[API Reference](api/core.md)** - Detailed API documentation

Ready to build something awesome? Let's go! 🚀