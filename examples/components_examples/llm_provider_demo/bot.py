import asyncio
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv
from pydantic import BaseModel

from botspot.components.new import llm_provider
from botspot.core.bot_manager import BotManager
from botspot.core.botspot_settings import BotspotSettings
from botspot.utils.internal import get_logger

logger = get_logger()

# Load environment variables
load_dotenv()


# Example Pydantic model for structured output
class NameAnalysis(BaseModel):
    name: str
    origin: str
    meaning: str
    popularity: int  # 1-10 scale


async def main():
    # Initialize the bot
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN not found in environment")

    bot = Bot(token=bot_token)
    dp = Dispatcher()

    # Configure settings for the LLM Provider component
    settings = BotspotSettings(
        # Enable the LLM Provider component
        llm_provider=llm_provider.LLMProviderSettings(
            enabled=True,
            default_model="claude-3.7",  # Can use shortcut name
            default_temperature=0.7,
            default_max_tokens=1000,
        ),
    )

    # Initialize BotManager with our settings
    bot_manager = BotManager(bot=bot, dispatcher=dp, **settings.model_dump())
    bot_manager.setup_dispatcher(dp)

    # Setup handlers
    @dp.message(Command("start"))
    async def handle_start(message: types.Message):
        await message.answer(
            "👋 Welcome to the LLM Provider demo bot!\n\n"
            "Available commands:\n"
            "/ask <question> - Ask a question to the LLM\n"
            "/analyze_name <name> - Get structured analysis of a name\n"
            "/stream <prompt> - See the LLM response appear word by word"
        )

    @dp.message(Command("ask"))
    async def handle_ask(message: types.Message):
        # Extract the question from the message
        question = message.text.replace("/ask", "", 1).strip()
        if not question:
            await message.answer("Please include a question after /ask")
            return

        # Send a "typing" action to show the bot is processing
        await message.answer("Thinking...")

        try:
            # Use the convience function that accesses the LLM Provider
            response = await llm_provider.aquery_llm(
                prompt=question,
                system_message="You are a helpful AI assistant. Keep answers concise and friendly.",
            )

            await message.answer(response)
        except Exception as e:
            logger.error(f"Error querying LLM: {e}")
            await message.answer(f"Sorry, I encountered an error: {str(e)}")

    @dp.message(Command("analyze_name"))
    async def handle_analyze_name(message: types.Message):
        # Extract the name from the message
        name = message.text.replace("/analyze_name", "", 1).strip()
        if not name:
            await message.answer("Please include a name after /analyze_name")
            return

        await message.answer(f"Analyzing the name '{name}'...")

        try:
            # Get the LLM Provider from the dependency manager
            provider = llm_provider.get_llm_provider()

            # Use structured output
            result = await provider.aquery_llm_structured(
                prompt=f"Analyze the name: {name}",
                output_schema=NameAnalysis,
                system_message=(
                    "You are a name analysis expert. "
                    "Analyze the given name and return its origin, meaning, "
                    "and popularity on a scale of 1-10."
                ),
            )

            # Format the response
            response = (
                f"📊 Analysis of '{result.name}':\n\n"
                f"🌍 Origin: {result.origin}\n"
                f"🔤 Meaning: {result.meaning}\n"
                f"📈 Popularity: {result.popularity}/10"
            )

            await message.answer(response)
        except Exception as e:
            logger.error(f"Error analyzing name: {e}")
            await message.answer(f"Sorry, I encountered an error: {str(e)}")

    @dp.message(Command("stream"))
    async def handle_stream(message: types.Message):
        # Extract the prompt from the message
        prompt = message.text.replace("/stream", "", 1).strip()
        if not prompt:
            await message.answer("Please include a prompt after /stream")
            return

        # Initial message that we'll update
        response_message = await message.answer("Generating response...")
        accumulated_text = ""

        try:
            # Get the LLM Provider
            provider = llm_provider.get_llm_provider()

            # Use streaming API
            async for chunk in provider.aquery_llm_stream(
                prompt=prompt,
                system_message="You are a helpful AI assistant.",
                model="claude-3.7",
            ):
                accumulated_text += chunk

                # Update the message periodically (not for every token to avoid rate limits)
                if len(accumulated_text) % 20 == 0:
                    await response_message.edit_text(accumulated_text)

                    # Small delay to make streaming visible
                    await asyncio.sleep(0.1)

            # Final update with complete text
            await response_message.edit_text(accumulated_text)
        except Exception as e:
            logger.error(f"Error streaming LLM response: {e}")
            await message.answer(f"Sorry, I encountered an error: {str(e)}")

    # Handle all regular messages
    @dp.message()
    async def handle_message(message: types.Message):
        if message.text:
            await handle_ask(message)  # Treat regular messages as questions

    # Start the bot
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
