import json
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, AsyncGenerator, Generator, Optional, Type, Union

from pydantic import BaseModel
from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger
from botspot.utils.send_safe import send_safe
from botspot.utils.user_ops import UserLike, compare_users_async

if TYPE_CHECKING:
    from litellm.types.utils import ModelResponse  # noqa: F401


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
    allow_everyone: bool = False  # If False, only friends and admins can use LLM features

    skip_import_check: bool = False  # Skip import check for dependencies

    class Config:
        env_prefix = "BOTSPOT_LLM_PROVIDER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Model name mapping for shortcuts
# This maps simple names to the provider-specific model names
MODEL_NAME_SHORTCUTS = {
    # Anthropic (Claude models)
    "claude-3.5": "anthropic/claude-3-5-sonnet-20241022",
    "claude-3.7-max": "anthropic/claude-3-7-sonnet-max",
    # OpenAI models
    "gpt-4o": "openai/gpt-4o",
    "o1": "openai/o1",
    # Google models
    "gemini-2.5": "google/gemini-2.5-pro-max",
    "gemini-2.5-max": "google/gemini-2.5-pro-max",
    "gemini-2.0-pro": "google/gemini-2.0-pro-exp",
    "gemini-2.0": "google/gemini-2.0-pro-exp",
    # xAI models
    "grok-2": "grok/grok-2",
    "gpt-4.5": "openai/gpt-4.5-preview",
    # Remaining models
    # Claude models (continued)
    "claude-3-opus": "anthropic/claude-3-opus",
    "claude-3.5-haiku": "anthropic/claude-3-5-haiku",
    "claude-3.5-sonnet": "anthropic/claude-3-5-sonnet",
    "claude-3.7": "anthropic/claude-3-7-sonnet",
    # OpenAI models (continued)
    "gpt-3.5": "openai/gpt-3.5-turbo",
    "gpt-4": "openai/gpt-4",
    "gpt-4-turbo": "openai/gpt-4-turbo-2024-04-09",
    "gpt-4.5-preview": "openai/gpt-4.5-preview",
    "gpt-4o-mini": "openai/gpt-4o-mini",
    "o1-mini": "openai/o1-mini",
    "o1-preview": "openai/o1-preview",
    "o3-mini": "openai/o3-mini",
    # Google models (continued)
    "gemini-2.0-flash": "google/gemini-2.0-flash",
    "gemini-2.0-flash-exp": "google/gemini-2.0-flash-thinking-exp",
    "gemini-2.5-exp": "google/gemini-2.5-pro-exp-03-25",
    "gemini-exp-1206": "google/gemini-exp-1206",
    # Cursor models
    "cursor-fast": "cursor/cursor-fast",
    "cursor-small": "cursor/cursor-small",
    # Deepseek models
    "deepseek-r1": "deepseek/deepseek-r1",
    "deepseek-v3": "deepseek/deepseek-v3",
    # Meta models
    "llama": "meta/llama",
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
    user: Optional[UserLike] = None


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
        # In-memory storage for usage stats if MongoDB is not available
        self.usage_stats = defaultdict(int)

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

    async def _check_user_allowed(self, user: Optional[UserLike]) -> bool:
        """
        Check if the user is allowed to use LLM features.

        Args:
            user: The user to check (can be ID, username, User object, etc.)

        Returns:
            True if allowed, False otherwise
        """
        from botspot.core.dependency_manager import get_dependency_manager

        deps = get_dependency_manager()

        # If allow everyone, always return True
        if self.settings.allow_everyone:
            return True

        # Check if single user mode is enabled
        if deps.botspot_settings.single_user_mode.enabled:
            if user is None:
                # In single user mode, if user not provided, assume it's the authorized user
                return True
            # Otherwise, check if the user matches the single user
            single_user = deps.botspot_settings.single_user_mode.user
            return await compare_users_async(user, single_user)

        # Check if user is admin or friend
        if user is not None:
            # Use enriched data for comparison if possible
            for admin in deps.botspot_settings.admins:
                if await compare_users_async(user, admin):
                    return True

            for friend in deps.botspot_settings.friends:
                if await compare_users_async(user, friend):
                    return True

        return False

    async def _track_usage(self, user: Optional[UserLike], model: str, tokens: int = 1):
        """
        Track LLM usage for the given user.

        Args:
            user: The user (ID, username, User object, etc.)
            model: The model used
            tokens: Number of tokens used (approximate)
        """
        from botspot.core.dependency_manager import get_dependency_manager
        from botspot.utils.user_ops import get_user_record_enriched, to_user_record

        deps = get_dependency_manager()

        # Try to get a consistent user key to use for tracking
        user_key = "unknown"
        if user is not None:
            # Get enriched record if possible
            if isinstance(user, (str, int)):
                record = await get_user_record_enriched(user)
            else:
                record = to_user_record(user)

            # Prefer user_id for tracking, but fallback to username
            if record.user_id:
                user_key = str(record.user_id)
            elif record.username:
                user_key = record.username
            else:
                user_key = str(user)

        # If MongoDB is enabled, store stats there
        # todo: adapt this to user
        if deps.botspot_settings.mongo_database.enabled and deps.mongo_database is not None:
            await deps.mongo_database.llm_usage.update_one(
                {"user": user_key},
                {"$inc": {f"models.{model}": tokens, "total": tokens}},
                upsert=True,
            )
        else:
            # Use in-memory storage
            self.usage_stats[user_key] += tokens

    def query_llm_raw(
        self,
        prompt: str,
        *,
        user: Optional[UserLike] = None,
        system_message: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        max_retries: int = 2,
        structured_output_schema: Optional[Type[BaseModel]] = None,
        **extra_kwargs,
    ) -> "ModelResponse":
        """
        Raw query to the LLM - returns the complete response object.

        Args:
            prompt: The text prompt to send to the model
            user: Optional user ID for access control and usage tracking
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
        import asyncio

        from litellm import completion

        from botspot.core.dependency_manager import get_dependency_manager

        deps = get_dependency_manager()

        # Check if in single_user_mode with no user provided
        if (
            deps.botspot_settings.single_user_mode.enabled
            and user is None
            and not self.settings.allow_everyone
        ):
            # Assume it's the single user
            user = deps.botspot_settings.single_user_mode.user
        elif not deps.botspot_settings.single_user_mode.enabled and user is None:
            # If not in single_user_mode and no user provided, raise exception
            from botspot.core.errors import LLMProviderError

            raise LLMProviderError("user is required when not in single_user_mode")

        # Check if user is allowed to use LLM
        if not asyncio.run(self._check_user_allowed(user)):
            chat_id = int(user) if isinstance(user, (int, str)) and str(user).isdigit() else None
            if chat_id:
                asyncio.run(
                    send_safe(
                        chat_id,
                        "You are not allowed to use LLM features. If you know the bot owner personally, "
                        "you can ask them to add you as a friend for unlimited usage.",
                    )
                )
            from botspot.core.errors import LLMPermissionError

            raise LLMPermissionError(f"User {user} is not allowed to use LLM features")

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
        response = completion(model=full_model_name, messages=messages, **params)

        # Track usage asynchronously (approximate tokens used)
        token_estimate = len(prompt) // 4 + max_tokens
        asyncio.run(self._track_usage(user, model, token_estimate))

        return response

    def query_llm_text(
        self,
        prompt: str,
        *,
        user: Optional[UserLike] = None,
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
            user=user,
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
        user: Optional[UserLike] = None,
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
        import asyncio

        from litellm import completion

        from botspot.core.dependency_manager import get_dependency_manager

        deps = get_dependency_manager()

        # Check if in single_user_mode with no user provided
        if (
            deps.botspot_settings.single_user_mode.enabled
            and user is None
            and not self.settings.allow_everyone
        ):
            # Assume it's the single user
            user = deps.botspot_settings.single_user_mode.user
        elif not deps.botspot_settings.single_user_mode.enabled and user is None:
            # If not in single_user_mode and no user provided, raise exception
            raise ValueError("user is required when not in single_user_mode")

        # Check if user is allowed to use LLM
        if not asyncio.run(self._check_user_allowed(user)):
            chat_id = int(user) if isinstance(user, (int, str)) and str(user).isdigit() else None
            if chat_id:
                asyncio.run(
                    send_safe(
                        chat_id,
                        "You are not allowed to use LLM features. If you know the bot owner personally, "
                        "you can ask them to add you as a friend for unlimited usage.",
                    )
                )
            raise PermissionError(f"User {user} is not allowed to use LLM features")

        # Get model parameters with defaults
        model = model or self.settings.default_model
        temperature = temperature if temperature is not None else self.settings.default_temperature
        max_tokens = max_tokens or self.settings.default_max_tokens
        timeout = timeout or self.settings.default_timeout

        # Get full model name
        full_model_name = self._get_full_model_name(model)

        # Prepare messages
        messages = self._prepare_messages(prompt, system_message)

        # Track usage at the start (approximate tokens)
        token_estimate = len(prompt) // 4 + max_tokens
        asyncio.run(self._track_usage(user, model, token_estimate))

        # Make the actual API call with streaming
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

    def query_llm_structured(
        self,
        prompt: str,
        output_schema: Type[BaseModel],
        *,
        user: Optional[UserLike] = None,
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
        import asyncio

        from litellm import completion

        from botspot.core.dependency_manager import get_dependency_manager

        deps = get_dependency_manager()

        # Check if in single_user_mode with no user provided
        if (
            deps.botspot_settings.single_user_mode.enabled
            and user is None
            and not self.settings.allow_everyone
        ):
            # Assume it's the single user
            user = deps.botspot_settings.single_user_mode.user
        elif not deps.botspot_settings.single_user_mode.enabled and user is None:
            # If not in single_user_mode and no user provided, raise exception
            raise ValueError("user is required when not in single_user_mode")

        # Check if user is allowed to use LLM
        if not asyncio.run(self._check_user_allowed(user)):
            chat_id = int(user) if isinstance(user, (int, str)) and str(user).isdigit() else None
            if chat_id:
                asyncio.run(
                    send_safe(
                        chat_id,
                        "You are not allowed to use LLM features. If you know the bot owner personally, "
                        "you can ask them to add you as a friend for unlimited usage.",
                    )
                )
            raise PermissionError(f"User {user} is not allowed to use LLM features")

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

        # Make the API call
        response = completion(
            model=full_model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            request_timeout=timeout,
            num_retries=max_retries,
            response_format=output_schema,
            **extra_kwargs,
        )

        # Track usage (approximate tokens)
        token_estimate = len(prompt) // 4 + len(response.choices[0].message.content)
        asyncio.run(self._track_usage(user, model, token_estimate))

        # Parse the response into the Pydantic model
        result_text = response.choices[0].message.content
        result_json = json.loads(result_text)
        return output_schema(**result_json)

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
        user: Optional[UserLike] = None,
        system_message: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        max_retries: int = 2,
        structured_output_schema: Optional[Type[BaseModel]] = None,
        **extra_kwargs,
    ) -> "ModelResponse":
        """
        Async raw query to the LLM - returns the complete response object.

        Args are the same as query_llm_raw but using async/await.
        """
        from litellm import acompletion

        from botspot.core.dependency_manager import get_dependency_manager

        deps = get_dependency_manager()

        # Check if in single_user_mode with no user provided
        if (
            deps.botspot_settings.single_user_mode.enabled
            and user is None
            and not self.settings.allow_everyone
        ):
            # Assume it's the single user
            user = deps.botspot_settings.single_user_mode.user
        elif not deps.botspot_settings.single_user_mode.enabled and user is None:
            # If not in single_user_mode and no user provided, raise exception
            raise ValueError("user is required when not in single_user_mode")

        # Check if user is allowed to use LLM
        if not await self._check_user_allowed(user):
            chat_id = int(user) if isinstance(user, (int, str)) and str(user).isdigit() else None
            if chat_id:
                await send_safe(
                    chat_id,
                    "You are not allowed to use LLM features. If you know the bot owner personally, "
                    "you can ask them to add you as a friend for unlimited usage.",
                )
            raise PermissionError(f"User {user} is not allowed to use LLM features")

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
        response = await acompletion(model=full_model_name, messages=messages, **params)

        # Track usage asynchronously (approximate tokens used)
        token_estimate = len(prompt) // 4 + max_tokens
        await self._track_usage(user, model, token_estimate)

        return response

    async def aquery_llm_text(
        self,
        prompt: str,
        *,
        user: Optional[UserLike] = None,
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
            user=user,
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
        user: Optional[UserLike] = None,
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

        from botspot.core.dependency_manager import get_dependency_manager

        deps = get_dependency_manager()

        # Check if in single_user_mode with no user provided
        if (
            deps.botspot_settings.single_user_mode.enabled
            and user is None
            and not self.settings.allow_everyone
        ):
            # Assume it's the single user
            user = deps.botspot_settings.single_user_mode.user
        elif not deps.botspot_settings.single_user_mode.enabled and user is None:
            # If not in single_user_mode and no user provided, raise exception
            raise ValueError("user is required when not in single_user_mode")

        # Check if user is allowed to use LLM
        if not await self._check_user_allowed(user):
            chat_id = int(user) if isinstance(user, (int, str)) and str(user).isdigit() else None
            if chat_id:
                await send_safe(
                    chat_id,
                    "You are not allowed to use LLM features. If you know the bot owner personally, "
                    "you can ask them to add you as a friend for unlimited usage.",
                )
            raise PermissionError(f"User {user} is not allowed to use LLM features")

        # Get model parameters with defaults
        model = model or self.settings.default_model
        temperature = temperature if temperature is not None else self.settings.default_temperature
        max_tokens = max_tokens or self.settings.default_max_tokens
        timeout = timeout or self.settings.default_timeout

        # Get full model name
        full_model_name = self._get_full_model_name(model)

        # Prepare messages
        messages = self._prepare_messages(prompt, system_message)

        # Track usage at the start (approximate tokens)
        token_estimate = len(prompt) // 4 + max_tokens
        await self._track_usage(user, model, token_estimate)

        # Make the actual API call with streaming
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

    async def aquery_llm_structured(
        self,
        prompt: str,
        output_schema: Type[BaseModel],
        *,
        user: Optional[UserLike] = None,
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

        from botspot.core.dependency_manager import get_dependency_manager

        deps = get_dependency_manager()

        # Check if in single_user_mode with no user provided
        if (
            deps.botspot_settings.single_user_mode.enabled
            and user is None
            and not self.settings.allow_everyone
        ):
            # Assume it's the single user
            user = deps.botspot_settings.single_user_mode.user
        elif not deps.botspot_settings.single_user_mode.enabled and user is None:
            # If not in single_user_mode and no user provided, raise exception
            raise ValueError("user is required when not in single_user_mode")

        # Check if user is allowed to use LLM
        if not await self._check_user_allowed(user):
            chat_id = int(user) if isinstance(user, (int, str)) and str(user).isdigit() else None
            if chat_id:
                await send_safe(
                    chat_id,
                    "You are not allowed to use LLM features. If you know the bot owner personally, "
                    "you can ask them to add you as a friend for unlimited usage.",
                )
            raise PermissionError(f"User {user} is not allowed to use LLM features")

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

        # Make the API call
        response = await acompletion(
            model=full_model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            request_timeout=timeout,
            num_retries=max_retries,
            response_format=output_schema,
            **extra_kwargs,
        )

        # Track usage (approximate tokens)
        token_estimate = len(prompt) // 4 + len(response.choices[0].message.content)
        await self._track_usage(user, model, token_estimate)

        # Parse the response into the Pydantic model
        result_text = response.choices[0].message.content
        result_json = json.loads(result_text)
        return output_schema(**result_json)

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
    from aiogram import Router
    from aiogram.filters import Command
    from aiogram.types import Message

    from botspot.utils.admin_filter import AdminFilter

    router = Router(name="llm_provider")

    @router.message(Command("llm_usage"), AdminFilter())
    async def llm_usage_command(message: Message):
        """Handler for /llm_usage command - shows LLM usage statistics."""
        stats = await get_llm_usage_stats()

        if not stats:
            await message.reply("No LLM usage statistics available.")
            return

        # Format stats nicely
        lines = ["📊 **LLM Usage Statistics**"]

        for user_id, user_stats in stats.items():
            if isinstance(user_stats, dict) and "total" in user_stats:
                models_str = ""
                if "models" in user_stats and user_stats["models"]:
                    models_list = [
                        f"{model}: {count}" for model, count in user_stats["models"].items()
                    ]
                    models_str = f" ({', '.join(models_list)})"

                lines.append(f"User {user_id}: {user_stats['total']} tokens{models_str}")
            else:
                lines.append(f"User {user_id}: {user_stats} tokens")

        await message.reply("\n".join(lines))

    dp.include_router(router)
    return dp


def initialize(settings: LLMProviderSettings) -> Optional[LLMProvider]:
    """Initialize the LLM Provider component."""
    if not settings.enabled:
        logger.info("LLM Provider component is disabled")
        return None

    # Check if litellm is installed
    try:
        import litellm

        logger.debug("litellm version: %s", litellm.api_version)
    except ImportError:
        logger.error(
            "litellm is not installed. Please install it to use the LLM Provider component."
        )
        raise
    if not settings.skip_import_check:
        ai_libraries = {
            "openai": "openai",  # poetry add openai -> import openai
            "anthropic": "anthropic",  # poetry add anthropic -> import anthropic
            "google-generativeai": "google.generativeai",  # poetry add google-generativeai -> import google.generativeai
            "xai_sdk": "xai",  # poetry add xai_sdk -> import xai
            # "huggingface": "transformers",  # poetry add huggingface -> import transformers
            # "cohere": "cohere",  # poetry add cohere -> import cohere
            # "mistralai": "mistralai",  # poetry add mistralai -> import mistralai
            # "deepseek": "deepseek",  # poetry add deepseek -> import deepseek
            # "fireworks-ai": "fireworks",  # poetry add fireworks-ai -> import fireworks
        }
        api_keys_env_names = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "google-generativeai": "GEMINI_API_KEY",
            "xai_sdk": "XAI_API_KEY",
            "huggingface": "HUGGINGFACE_TOKEN",
            "cohere": "COHERE_API_KEY",
            "mistralai": "MISTRAL_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "fireworks-ai": "FIREWORKS_API_KEY",
        }
        # Check for specific libraries and report to the user
        installed_libraries = []
        for lib_name, lib in ai_libraries.items():
            try:
                __import__(lib)
                installed_libraries.append(lib_name)
                msg = f"✅ {lib_name} is available."
                # todo: check api key, if not -> print warning
                env_key = api_keys_env_names.get(lib_name)
                api_key = os.getenv(env_key)

                if api_key:
                    msg += f" (✅ {env_key})"
                else:
                    msg += f" (⚠️ No {env_key})"
                logger.info(msg)
            except ImportError:
                logger.info(
                    f"❌ {lib_name} is not installed. `poetry add {lib_name}` to install it."
                )

        if not installed_libraries:
            keys = list(ai_libraries.keys())
            logger.error(
                "At least one of the required libraries (openai, anthropic, gemini) must be installed.\n"
                f"None of the required libraries {keys} are installed."
            )
            raise ImportError(
                f"At least one of the required libraries {keys} must be installed.\n"
                "set BOTSPOT_LLM_PROVIDER_SKIP_IMPORT_CHECK=1 to skip this check or install the required libraries."
            )

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
def query_llm_text(
    prompt: str,
    *,
    user: Optional[Union[int, str]] = None,
    system_message: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs,
) -> str:
    """
    Query the LLM and return the text response.

    This is a convenience function that uses the global LLM provider.
    """
    provider = get_llm_provider()
    return provider.query_llm_text(
        prompt=prompt, user=user, system_message=system_message, model=model, **kwargs
    )


def query_llm_raw(
    prompt: str,
    *,
    user: Optional[Union[int, str]] = None,
    system_message: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs,
) -> "ModelResponse":
    """
    Raw query to the LLM - returns the complete response object.

    This is a convenience function that uses the global LLM provider.

    Args:
        prompt: The text prompt to send to the LLM
        user: User identifier for tracking usage and permissions
        system_message: Optional system message to prepend
        model: Optional model to use (defaults to provider default)
        **kwargs: Additional arguments to pass to the LLM provider

    Returns:
        Raw response from the LLM with full metadata and usage stats
    """
    provider = get_llm_provider()
    return provider.query_llm_raw(
        prompt=prompt, user=user, system_message=system_message, model=model, **kwargs
    )


def query_llm_structured(
    prompt: str,
    output_schema: Type[BaseModel],
    *,
    user: Optional[Union[int, str]] = None,
    system_message: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs,
) -> BaseModel:
    """
    Query LLM with structured output.

    This is a convenience function that uses the global LLM provider.

    Args:
        prompt: The text prompt to send to the LLM
        output_schema: A Pydantic model class defining the structure
        user: User identifier for tracking usage and permissions
        system_message: Optional system message to prepend
        model: Optional model to use (defaults to provider default)
        **kwargs: Additional arguments to pass to the LLM provider

    Returns:
        An instance of the provided Pydantic model
    """
    provider = get_llm_provider()
    return provider.query_llm_structured(
        prompt=prompt,
        output_schema=output_schema,
        user=user,
        system_message=system_message,
        model=model,
        **kwargs,
    )


async def aquery_llm_text(
    prompt: str,
    *,
    user: Optional[Union[int, str]] = None,
    system_message: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs,
) -> str:
    """
    Async query the LLM and return the text response.

    This is a convenience function that uses the global LLM provider.
    """
    provider = get_llm_provider()
    return await provider.aquery_llm_text(
        prompt=prompt, user=user, system_message=system_message, model=model, **kwargs
    )


async def astream_llm(
    prompt: str,
    *,
    user: Optional[Union[int, str]] = None,
    system_message: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs,
) -> AsyncGenerator[str, None]:
    """
    Async stream text chunks from the LLM.

    This is a convenience function that uses the global LLM provider.

    Args:
        prompt: The text prompt to send to the LLM
        user: User identifier for tracking usage and permissions
        system_message: Optional system message to prepend
        model: Optional model to use (defaults to provider default)
        **kwargs: Additional arguments to pass to the LLM provider

    Returns:
        An async generator that yields text chunks as they become available
    """
    provider = get_llm_provider()
    async for chunk in provider.aquery_llm_stream(
        prompt=prompt, user=user, system_message=system_message, model=model, **kwargs
    ):
        yield chunk


async def aquery_llm_structured(
    prompt: str,
    output_schema: Type[BaseModel],
    *,
    user: Optional[Union[int, str]] = None,
    system_message: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs,
) -> BaseModel:
    """
    Async query LLM with structured output.

    This is a convenience function that uses the global LLM provider.

    Args:
        prompt: The text prompt to send to the LLM
        output_schema: A Pydantic model class defining the structure
        user: User identifier for tracking usage and permissions
        system_message: Optional system message to prepend
        model: Optional model to use (defaults to provider default)
        **kwargs: Additional arguments to pass to the LLM provider

    Returns:
        An instance of the provided Pydantic model
    """
    provider = get_llm_provider()
    return await provider.aquery_llm_structured(
        prompt=prompt,
        output_schema=output_schema,
        user=user,
        system_message=system_message,
        model=model,
        **kwargs,
    )


async def aquery_llm_raw(
    prompt: str,
    *,
    user: Optional[Union[int, str]] = None,
    system_message: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs,
) -> "ModelResponse":
    """
    Async raw query to the LLM - returns the complete response object.

    This is a convenience function that uses the global LLM provider.

    Args:
        prompt: The text prompt to send to the LLM
        user: User identifier for tracking usage and permissions
        system_message: Optional system message to prepend
        model: Optional model to use (defaults to provider default)
        **kwargs: Additional arguments to pass to the LLM provider

    Returns:
        Raw response from the LLM with full metadata and usage stats
    """
    provider = get_llm_provider()
    return await provider.aquery_llm_raw(
        prompt=prompt, user=user, system_message=system_message, model=model, **kwargs
    )


# todo: adapt this to user not user_id
async def get_llm_usage_stats(user: Optional[UserLike] = None) -> dict:
    """
    Get LLM usage statistics.

    Args:
        user: Optional user ID to filter stats for a specific user

    Returns:
        Dictionary with usage statistics
    """
    provider = get_llm_provider()
    from botspot.core.dependency_manager import get_dependency_manager

    deps = get_dependency_manager()

    # Check if MongoDB is available
    if deps.botspot_settings.mongo_database.enabled and deps.mongo_database is not None:
        query = {}
        if user is not None:
            query["user"] = str(user)

        cursor = deps.mongo_database.llm_usage.find(query)
        stats = {}
        async for doc in cursor:
            stats[doc["user"]] = {
                "models": doc.get("models", {}),
                "total": doc.get("total", 0),
            }
        return stats

    # Use in-memory stats
    if user is not None:
        user_key = str(user)
        if user_key in provider.usage_stats:
            return {user_key: provider.usage_stats[user_key]}
        return {}

    return provider.usage_stats


# ---------------------------------------------
# endregion Utils
# ---------------------------------------------


if __name__ == "__main__":
    import asyncio

    from aiogram.types import Message
    from pydantic import BaseModel

    class MovieRecommendation(BaseModel):
        title: str
        year: int
        reasons: list[str]

    async def llm_message_handler(message: Message):
        prompt = message.text
        user_id = message.from_user.id
        provider = get_llm_provider()

        # 1. Basic text query
        response = await aquery_llm_text(
            prompt=prompt, user=user_id, model="claude-3.5", temperature=0.7
        )
        print(f"Basic text response: {response}")

        # 2. Streaming response (to show output token by token)
        print("\nStreaming response:")
        async for chunk in astream_llm(prompt="Tell me a short story", user=user_id):
            print(chunk, end="", flush=True)

        # 3. Structured output with Pydantic
        structured_result = await provider.aquery_llm_structured(
            prompt="Recommend a sci-fi movie", output_schema=MovieRecommendation, user=user_id
        )
        print(f"\n\nMovie: {structured_result.title} ({structured_result.year})")

        # 4. Raw response with full details
        raw_response = await provider.aquery_llm_raw(
            prompt="What's the weather like?", user=user_id
        )
        print(f"\nToken usage: {raw_response.usage}")

    # Run the example with a mock message
    asyncio.run(
        llm_message_handler(Message(text="What is the meaning of life?", from_user={"id": 12345}))
    )
