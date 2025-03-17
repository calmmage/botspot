"""LLM Provider Component for Botspot

This module provides a LLM (Large Language Model) interface for Botspot,
using litellm as the backend client to support multiple LLM providers.
"""

import json
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Generator, Optional, Type

from pydantic import BaseModel
from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger

logger = get_logger()


# ---------------------------------------------
# region Settings and Configuration
# ---------------------------------------------


class LLMProviderSettings(BaseSettings):
    """Settings for the LLM Provider component."""

    enabled: bool = False
    default_model: str = "claude-3.7"  # Default model to use
    default_temperature: float = 0.7
    default_max_tokens: int = 1000
    default_timeout: int = 30

    class Config:
        env_prefix = "BOTSPOT_LLM_PROVIDER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Model name mapping for shortcuts
# This maps simple names to the provider-specific model names
MODEL_NAME_SHORTCUTS = {
    # Claude models
    "claude-3.7": "anthropic/claude-3-5-sonnet-20240620",
    "claude-3.5": "anthropic/claude-3-5-sonnet-20240620",
    "claude-3-haiku": "anthropic/claude-3-haiku-20240307",
    "claude-3-sonnet": "anthropic/claude-3-sonnet-20240229",
    "claude-3-opus": "anthropic/claude-3-opus-20240229",
    "claude-2": "anthropic/claude-2",
    # OpenAI models
    "gpt-4o": "openai/gpt-4o",
    "gpt-4-turbo": "openai/gpt-4-turbo",
    "gpt-4.5": "openai/gpt-4-turbo",  # Alias for gpt-4-turbo
    "gpt-4": "openai/gpt-4",
    "gpt-3.5": "openai/gpt-3.5-turbo",
    # Other models
    "gemini-pro": "google/gemini-pro",
    "gemini-1.5": "google/gemini-1.5-pro",
    "gemini-2": "google/gemini-2",
    "grok": "grok/grok",
    "grok3": "grok/grok-3",
}


@dataclass
class LLMModelParams:
    """Parameters for configuring the LLM model"""

    model: str = "claude-3.7"
    temperature: float = 0.7
    max_tokens: int = 1000
    timeout: Optional[float] = None
    max_retries: int = 2
    streaming: bool = False


@dataclass
class LLMQueryParams:
    """Parameters for the query itself"""

    system_message: Optional[str] = None
    use_structured_output: bool = False
    structured_output_schema: Optional[Any] = None


# ---------------------------------------------
# endregion Settings and Configuration
# ---------------------------------------------


# ---------------------------------------------
# region LLM Provider Implementation
# ---------------------------------------------


class LLMProvider:
    """Main LLM Provider class for Botspot"""

    def __init__(self, settings: LLMProviderSettings):
        """Initialize the LLM Provider with the given settings."""
        self.settings = settings

    def _get_full_model_name(self, model: str) -> str:
        """Convert a model shortcut to its full name for litellm."""
        if "/" in model:  # Already a full name
            return model
        return MODEL_NAME_SHORTCUTS.get(model, model)

    def _prepare_messages(self, prompt: str, system_message: Optional[str] = None) -> list:
        """Prepare messages for the LLM request."""
        messages = []

        # Add system message if provided
        if system_message:
            messages.append({"role": "system", "content": system_message})

        # Add user prompt
        messages.append({"role": "user", "content": prompt})

        return messages

    # ---------------------------------------------
    # region Synchronous Query Methods
    # ---------------------------------------------

    def query_llm_raw(
        self,
        prompt: str,
        *,
        system_message: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        max_retries: int = 2,
        structured_output_schema: Optional[Type[BaseModel]] = None,
        **extra_kwargs,
    ) -> Any:
        """
        Raw query to the LLM - returns the complete response object.

        Args:
            prompt: The text prompt to send to the model
            system_message: Optional system message for the model
            model: Model name to use (can be a shortcut)
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
            timeout: Request timeout
            max_retries: Number of times to retry failed requests
            structured_output_schema: Optional Pydantic model for structured output
            **extra_kwargs: Additional arguments to pass to the LLM

        Returns:
            Raw response from the LLM
        """
        from litellm import completion

        # Get model parameters with defaults
        model = model or self.settings.default_model
        temperature = temperature if temperature is not None else self.settings.default_temperature
        max_tokens = max_tokens or self.settings.default_max_tokens
        timeout = timeout or self.settings.default_timeout

        # Get full model name
        full_model_name = self._get_full_model_name(model)

        # Prepare messages
        messages = self._prepare_messages(prompt, system_message)

        # Additional parameters
        params = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "request_timeout": timeout,
            "num_retries": max_retries,
            **extra_kwargs,
        }

        # Add structured output if needed
        if structured_output_schema:
            params["response_format"] = structured_output_schema

        logger.debug(f"Querying LLM with model {full_model_name}")

        # Make the actual API call
        try:

            response = completion(model=full_model_name, messages=messages, **params)
            return response
        except Exception as e:
            logger.error(f"Error querying LLM: {e}")
            raise

    def query_llm_text(
        self,
        prompt: str,
        *,
        system_message: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        max_retries: int = 2,
        **extra_kwargs,
    ) -> str:
        """
        Query the LLM and return just the text response.

        Arguments are the same as query_llm_raw but returns a string.
        """
        response = self.query_llm_raw(
            prompt=prompt,
            system_message=system_message,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
            **extra_kwargs,
        )
        return response.choices[0].message.content

    def query_llm_stream(
        self,
        prompt: str,
        *,
        system_message: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        max_retries: int = 2,
        **extra_kwargs,
    ) -> Generator[str, None, None]:
        """
        Stream text chunks from the LLM.

        Arguments are the same as query_llm_raw but returns a generator of text chunks.
        """
        from litellm import completion

        # Get model parameters with defaults
        model = model or self.settings.default_model
        temperature = temperature if temperature is not None else self.settings.default_temperature
        max_tokens = max_tokens or self.settings.default_max_tokens
        timeout = timeout or self.settings.default_timeout

        # Get full model name
        full_model_name = self._get_full_model_name(model)

        # Prepare messages
        messages = self._prepare_messages(prompt, system_message)

        # Make the actual API call with streaming
        try:
            response = completion(
                model=full_model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                request_timeout=timeout,
                num_retries=max_retries,
                stream=True,
                **extra_kwargs,
            )

            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"Error streaming from LLM: {e}")
            raise

    def query_llm_structured(
        self,
        prompt: str,
        output_schema: Type[BaseModel],
        *,
        system_message: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        max_retries: int = 2,
        **extra_kwargs,
    ) -> BaseModel:
        """
        Query LLM with structured output.

        Args:
            output_schema: A Pydantic model class defining the structure
            Other arguments same as query_llm_raw

        Returns:
            An instance of the provided Pydantic model
        """
        from litellm import completion

        # Get model parameters with defaults
        model = model or self.settings.default_model
        temperature = temperature if temperature is not None else self.settings.default_temperature
        max_tokens = max_tokens or self.settings.default_max_tokens
        timeout = timeout or self.settings.default_timeout

        # Get full model name
        full_model_name = self._get_full_model_name(model)

        # Prepare messages and add structured output instructions
        enhanced_system = system_message or ""
        enhanced_system += (
            "\nYou MUST respond with a valid JSON object that conforms to the specified schema."
        )

        messages = self._prepare_messages(prompt, enhanced_system)

        try:
            # Make the API call
            response = completion(
                model=full_model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                request_timeout=timeout,
                num_retries=max_retries,
                response_format={"type": "json_object"},
                **extra_kwargs,
            )

            # Parse the response into the Pydantic model
            result_text = response.choices[0].message.content
            result_json = json.loads(result_text)
            return output_schema(**result_json)
        except Exception as e:
            logger.error(f"Error getting structured output from LLM: {e}")
            raise

    # ---------------------------------------------
    # endregion Synchronous Query Methods
    # ---------------------------------------------

    # ---------------------------------------------
    # region Asynchronous Query Methods
    # ---------------------------------------------

    async def aquery_llm_raw(
        self,
        prompt: str,
        *,
        system_message: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        max_retries: int = 2,
        structured_output_schema: Optional[Type[BaseModel]] = None,
        **extra_kwargs,
    ) -> Any:
        """
        Async raw query to the LLM - returns the complete response object.

        Args are the same as query_llm_raw but using async/await.
        """
        from litellm import acompletion

        # Get model parameters with defaults
        model = model or self.settings.default_model
        temperature = temperature if temperature is not None else self.settings.default_temperature
        max_tokens = max_tokens or self.settings.default_max_tokens
        timeout = timeout or self.settings.default_timeout

        # Get full model name
        full_model_name = self._get_full_model_name(model)

        # Prepare messages
        messages = self._prepare_messages(prompt, system_message)

        # Additional parameters
        params = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "request_timeout": timeout,
            "num_retries": max_retries,
            **extra_kwargs,
        }

        # Add structured output if needed
        if structured_output_schema:
            params["response_format"] = structured_output_schema

        logger.debug(f"Async querying LLM with model {full_model_name}")

        # Make the actual API call
        try:
            response = await acompletion(model=full_model_name, messages=messages, **params)
            return response
        except Exception as e:
            logger.error(f"Error in async query to LLM: {e}")
            raise

    async def aquery_llm_text(
        self,
        prompt: str,
        *,
        system_message: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        max_retries: int = 2,
        **extra_kwargs,
    ) -> str:
        """
        Async query to the LLM returning just the text response.

        Arguments are the same as aquery_llm_raw but returns a string.
        """
        response = await self.aquery_llm_raw(
            prompt=prompt,
            system_message=system_message,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
            **extra_kwargs,
        )
        return response.choices[0].message.content

    async def aquery_llm_stream(
        self,
        prompt: str,
        *,
        system_message: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        max_retries: int = 2,
        **extra_kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Async stream text chunks from the LLM.

        Arguments are the same as aquery_llm_raw but returns an async generator of text chunks.
        """
        from litellm import acompletion

        # Get model parameters with defaults
        model = model or self.settings.default_model
        temperature = temperature if temperature is not None else self.settings.default_temperature
        max_tokens = max_tokens or self.settings.default_max_tokens
        timeout = timeout or self.settings.default_timeout

        # Get full model name
        full_model_name = self._get_full_model_name(model)

        # Prepare messages
        messages = self._prepare_messages(prompt, system_message)

        # Make the actual API call with streaming
        try:
            response = await acompletion(
                model=full_model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                request_timeout=timeout,
                num_retries=max_retries,
                stream=True,
                **extra_kwargs,
            )

            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"Error async streaming from LLM: {e}")
            raise

    async def aquery_llm_structured(
        self,
        prompt: str,
        output_schema: Type[BaseModel],
        *,
        system_message: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        max_retries: int = 2,
        **extra_kwargs,
    ) -> BaseModel:
        """
        Async query LLM with structured output.

        Args:
            output_schema: A Pydantic model class defining the structure
            Other arguments same as aquery_llm_raw

        Returns:
            An instance of the provided Pydantic model
        """
        from litellm import acompletion

        # Get model parameters with defaults
        model = model or self.settings.default_model
        temperature = temperature if temperature is not None else self.settings.default_temperature
        max_tokens = max_tokens or self.settings.default_max_tokens
        timeout = timeout or self.settings.default_timeout

        # Get full model name
        full_model_name = self._get_full_model_name(model)

        # Prepare messages and add structured output instructions
        enhanced_system = system_message or ""
        enhanced_system += (
            "\nYou MUST respond with a valid JSON object that conforms to the specified schema."
        )

        messages = self._prepare_messages(prompt, enhanced_system)

        try:
            # Make the API call
            response = await acompletion(
                model=full_model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                request_timeout=timeout,
                num_retries=max_retries,
                response_format={"type": "json_object"},
                **extra_kwargs,
            )

            # Parse the response into the Pydantic model
            result_text = response.choices[0].message.content
            result_json = json.loads(result_text)
            return output_schema(**result_json)
        except Exception as e:
            logger.error(f"Error getting async structured output from LLM: {e}")
            raise

    # ---------------------------------------------
    # endregion Asynchronous Query Methods
    # ---------------------------------------------


# ---------------------------------------------
# endregion LLM Provider Implementation
# ---------------------------------------------


# ---------------------------------------------
# region Initialization and Dispatcher Setup
# ---------------------------------------------


def setup_dispatcher(dp):
    """Set up the dispatcher with LLM provider component."""
    return dp


def initialize(settings: LLMProviderSettings) -> LLMProvider:
    """Initialize the LLM Provider component."""
    if not settings.enabled:
        raise RuntimeError("LLM Provider component is disabled")

    logger.info("Initializing LLM Provider component")
    provider = LLMProvider(settings)

    return provider


# ---------------------------------------------
# endregion Initialization and Dispatcher Setup
# ---------------------------------------------


# ---------------------------------------------
# region Utils
# ---------------------------------------------


def get_llm_provider() -> LLMProvider:
    """Get the LLM Provider from dependency manager."""
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()
    return deps.llm_provider


# Convenience functions for direct use
def query_llm(
    prompt: str, *, system_message: Optional[str] = None, model: Optional[str] = None, **kwargs
) -> str:
    """
    Query the LLM and return the text response.

    This is a convenience function that uses the global LLM provider.
    """
    provider = get_llm_provider()
    return provider.query_llm_text(
        prompt=prompt, system_message=system_message, model=model, **kwargs
    )


async def aquery_llm(
    prompt: str, *, system_message: Optional[str] = None, model: Optional[str] = None, **kwargs
) -> str:
    """
    Async query the LLM and return the text response.

    This is a convenience function that uses the global LLM provider.
    """
    provider = get_llm_provider()
    return await provider.aquery_llm_text(
        prompt=prompt, system_message=system_message, model=model, **kwargs
    )


# ---------------------------------------------
# endregion Utils
# ---------------------------------------------
