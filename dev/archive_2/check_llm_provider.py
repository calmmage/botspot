import asyncio

from litellm import Choices
from pydantic import BaseModel

# Your user ID
USER_ID = 291560340
# Model to use for testing
MODEL = "gpt-4.1-nano"


async def test_llm_provider():
    """Test all LLM provider functions."""
    from botspot.llm_provider import (
        aquery_llm_raw,
        aquery_llm_structured,
        aquery_llm_text,
        astream_llm,
    )

    print("\n=== Testing Text Query ===")
    response = await aquery_llm_text("Hello, how are you?", user=USER_ID, model=MODEL)
    print(f"Response: {response}")

    print("\n=== Testing Raw Query ===")
    raw_response = await aquery_llm_raw(
        "Hello, what's the weather like?", user=USER_ID, model=MODEL
    )
    # Handle the response safely
    try:
        assert isinstance(raw_response.choices[0], Choices)
        content = raw_response.choices[0].message.content
    except (AttributeError, IndexError):
        content = "No content"

    try:
        usage = raw_response.usage.total_tokens  # type: ignore # pyright: ignore
    except AttributeError:
        usage = "Unknown"

    print(f"Response content: {content}")
    print(f"Token usage: {usage}")

    print("\n=== Testing Structured Query ===")

    class MovieRating(BaseModel):
        movie: str
        rating: int

    class MovieRatings(BaseModel):
        movies: list[MovieRating]

    structured = await aquery_llm_structured(
        "Recommend me a couple of movies", output_schema=MovieRatings, user=USER_ID, model=MODEL
    )
    print("Movies:")
    for movie in structured.movies:
        print(f"- {movie.movie}: {movie.rating}/10")

    print("\n=== Testing Streaming ===")
    print("Response: ", end="")
    async for chunk in astream_llm("Tell me a short joke", user=USER_ID, model=MODEL):
        print(chunk, end="", flush=True)
    print("\n")


if __name__ == "__main__":
    from botspot.components.new.llm_provider import LLMProviderSettings
    from botspot.core.bot_manager import BotManager

    # Create LLM provider settings with allow_everyone=True
    llm_settings = LLMProviderSettings(enabled=True, allow_everyone=True)
    bm = BotManager(llm_provider_enabled=True, llm_provider_settings=llm_settings)

    # Add your user ID to admins
    bm.settings.admins_str = str(USER_ID)

    # Run the tests
    asyncio.run(test_llm_provider())
