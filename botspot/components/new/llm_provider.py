import asyncio
import base64
import json
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Dict,
    Optional,
    Sequence,
    Type,
    TypeVar,
    Union,
)

from aiogram.types import Chat, User
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger
from botspot.utils.send_safe import send_safe
from botspot.utils.unsorted import Attachment, download_telegram_file, get_attachment_format
from botspot.utils.user_ops import UserLike, compare_users_async

# todo: check max attachments for different models
# from botspot.utils.unsorted import download_telegram_file
# max attachments for each model
MAX_ATTACHMENTS = defaultdict(lambda: 10)

if TYPE_CHECKING:
    from litellm.types.utils import ModelResponse


logger = get_logger()


# ---------------------------------------------
# region Settings and Configuration
# ---------------------------------------------


class LLMProviderSettings(BaseSettings):
    """Settings for the LLM Provider component."""

    enabled: bool = False
    default_model: str = "claude-3.7"  # Default model to use (maps to claude-3-7-sonnet-latest)
    default_temperature: float = 0.7
    default_max_tokens: int = 1024
    default_timeout: int = 30
    # If False, only friends and admins can use LLM features
    allow_everyone: bool = False
    skip_import_check: bool = False  # Skip import check for dependencies
    drop_unsupported_params: bool = False

    class Config:
        env_prefix = "BOTSPOT_LLM_PROVIDER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Model name mapping for shortcuts
# This maps simple names to the provider-specific model names
MODEL_NAME_SHORTCUTS = {
    # -----------------------------------------------
    # main models
    # -----------------------------------------------
    # Anthropic Models
    "claude-3-5-haiku": "anthropic/claude-3-5-haiku-latest",  # $0.80 per 1M input, $4.00 per 1M output
    "claude-3-5-sonnet": "anthropic/claude-3-5-sonnet-latest",  # $3.00 per 1M input, $15.00 per 1M output
    "claude-3-7": "anthropic/claude-3-7-sonnet-latest",  # $3.00 per 1M input, $15.00 per 1M output
    "claude-3.5-haiku": "anthropic/claude-3-5-haiku-latest",  # $0.80 per 1M input, $4.00 per 1M output
    "claude-3.5-sonnet": "anthropic/claude-3-5-sonnet-latest",  # $3.00 per 1M input, $15.00 per 1M output
    "claude-3.7": "anthropic/claude-3-7-sonnet-latest",  # $3.00 per 1M input, $15.00 per 1M output
    "claude-4": "anthropic/claude-sonnet-4-20250514",  # $3 per 1M input, $15 per 1M output
    # OpenAI Models
    # Cheap
    "gpt-4o-mini": "openai/gpt-4o-mini",  # $0.15 per 1M input, $0.60 per 1M output
    "o4-mini": "openai/o4-mini",  # $0.55 per 1M input, $2.20 per 1M output
    "gpt-4.1-nano": "openai/gpt-4.1-nano",  # $0.10 per 1M input, $0.40 per 1M output (assumed)
    # Mid
    "gpt-4o": "openai/gpt-4o",  # $2.50 per 1M input, $10.00 per 1M output
    "gpt-4.1": "openai/gpt-4.1",  # $5.00 per 1M input, $15.00 per 1M output (assumed)
    # Max
    "o3": "openai/o3",  # $15.00 per 1M input, $60.00 per 1M output
    "gpt-4": "openai/gpt-4",  # $30.00 per 1M input, $60.00 per 1M output
    "o1-pro": "openai/o1-pro",  # $20.00 per 1M input, $80.00 per 1M output (assumed)
    # Google Models
    "gemini-2.5-flash": "gemini/gemini-2.5-flash-preview-04-17",  # $0.15 per 1M input, $0.60 per 1M output (non-thinking)
    "gemini-2.5-pro": "gemini/gemini-2.5-pro-preview-03-25",  # $1.25 per 1M input, $10.00 per 1M output
    "gemini-2.5-exp": "gemini/gemini-2.5-pro-exp-03-25",  # Free tier (updated to gemini-2.5-pro-preview-05-06 on 2025-05-06 with same pricing as gemini-2.5-pro)
    # xAI Models
    "grok-2": "xai/grok-2",  # $5.00 per 1M input, $15.00 per 1M output
    "grok-3-mini": "xai/grok-3-mini-beta",
    "grok-3": "xai/grok-3",  # Pricing not available
    # -----------------------------------------------
    # all other models
    # -----------------------------------------------
    # Anthropic (Claude models)
    # Claude 3.7 Sonnet
    # "claude-3.7": "anthropic/claude-3-7-sonnet-latest",  # hardcoded: claude-3-7-sonnet-20250219
    "claude-3.7-sonnet": "anthropic/claude-3-7-sonnet-latest",  # hardcoded: claude-3-7-sonnet-20250219
    "claude-4-sonnet": "anthropic/claude-sonnet-4-20250514",  # $3 per 1M input, $15 per 1M output
    "claude-4-opus": "anthropic/claude-4-opus-20250514",  # $15 per 1M input, $75 per 1M output
    "claude-3-7-sonnet-20250219": "anthropic/claude-3-7-sonnet-20250219",  # specific version
    # Claude 3.5 Models
    # "claude-3.5-haiku": "anthropic/claude-3-5-haiku-latest",  # hardcoded: claude-3-5-haiku-20241022
    "claude-3.5": "anthropic/claude-3-5-sonnet-latest",  # hardcoded: claude-3-5-sonnet-20241022
    "claude-3-5": "anthropic/claude-3-5-sonnet-latest",  # hardcoded: claude-3-5-sonnet-20241022
    # "claude-3.5-sonnet": "anthropic/claude-3-5-sonnet-latest",  # hardcoded: claude-3-5-sonnet-20241022
    "claude-3-5-sonnet-20241022": "anthropic/claude-3-5-sonnet-20241022",  # specific version
    "claude-3.5-sonnet-v1": "anthropic/claude-3-5-sonnet-20240620",
    "claude-3.5-sonnet-20240620": "anthropic/claude-3-5-sonnet-20240620",
    # OpenAI models
    # "gpt-4o": "openai/gpt-4o",
    "o1": "openai/o1",
    # Google models
    # "gemini-2.5": "gemini/gemini-2.5-pro-max",
    "gemini-2.5-max": "gemini/gemini-2.5-pro-max",
    # "gemini-2.5-exp": "gemini/gemini-2.5-pro-exp-03-25",
    # "gemini-2.0-pro": "gemini/gemini-2.0-pro-exp",
    "gemini-2.0": "gemini/gemini-2.0-pro-exp",
    # xAI models
    # "grok-2": "grok/grok-2",
    # "grok-3": "grok/grok-3",
    "gpt-4.5": "openai/gpt-4.5-preview",
    # Remaining models
    # OpenAI models (continued)
    # "gpt-3.5": "openai/gpt-3.5-turbo",
    # "gpt-4": "openai/gpt-4",
    "gpt-4-turbo": "openai/gpt-4-turbo-2024-04-09",
    # "gpt-4.5-preview": "openai/gpt-4.5-preview",
    # "gpt-4o-mini": "openai/gpt-4o-mini",
    "o1-mini": "openai/o1-mini",
    "o1-preview": "openai/o1-preview",
    "o3-mini": "openai/o3-mini",
    # Google models (continued)
    # "gemini-2.0-flash": "gemini/gemini-2.0-flash",
    "gemini-2.0-flash-exp": "gemini/gemini-2.0-flash-thinking-exp",
    "gemini-exp-1206": "gemini/gemini-exp-1206",
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

# Define a TypeVar for generic model types
T = TypeVar("T", bound=BaseModel)


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

    async def _aprepare_messages(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        attachments: Optional[Sequence[Union[Attachment, bytes]]] = None,
    ) -> list:
        """Prepare messages for the LLM request."""
        messages = []

        # Add system message if provided
        if system_message:
            messages.append({"role": "system", "content": system_message})

        if attachments is None or not attachments:
            content = prompt
        else:
            content = [{"type": "text", "text": prompt}]
            for attachment in attachments:
                if isinstance(attachment, Attachment):
                    file_stream = await download_telegram_file(attachment)
                    file_bytes = file_stream.read()
                else:
                    file_bytes = attachment
                # assert isinstance(file, BinaryIO)
                assert isinstance(file_bytes, bytes)

                encoded_file = base64.b64encode(file_bytes).decode("utf-8")
                # todo: figure out the proper way to include mime type - for now, do hardcoded as it worked before

                if isinstance(attachment, Attachment):
                    format = get_attachment_format(attachment)
                    image_url = f"data:{format};base64,{encoded_file}"
                else:
                    # todo: check if this even works
                    # todo: figure out to provide mime type here - need to pass with the bytes somehow / as a file. BinaryIO?
                    logger.warning(
                        f"received non-telegram file as attachment: {attachment}, using without mime type"
                    )
                    image_url = f"base64,{encoded_file}"

                content.append(
                    {
                        "type": "image_url",
                        "image_url": image_url,
                    }
                )
        # Add user prompt
        messages.append({"role": "user", "content": content})

        return messages

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
            assert single_user is not None, "Single user mode is enabled but user is not set"
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

    async def _prepare_request(
        self,
        prompt: str,
        *,
        user: Optional[UserLike] = None,
        system_message: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        structured_output_schema: Optional[Type[BaseModel]] = None,
        attachments: Optional[Sequence[Union[Attachment, bytes]]] = None,
    ) -> Dict[str, Any]:
        """
        Prepare common parameters for LLM requests.

        This centralizes the parameter preparation logic for all query methods.

        Returns:
            Dictionary with processed parameters for the request
        """
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
        model_name = model or self.settings.default_model
        temperature = temperature if temperature is not None else self.settings.default_temperature
        max_tokens = max_tokens or self.settings.default_max_tokens
        timeout = timeout or self.settings.default_timeout

        # O-series models only support temperature=1
        if self._is_o_series_model(model_name) and temperature != 1:
            logger.warning(
                f"O-series model '{model_name}' only supports temperature=1. Overriding temperature {temperature} -> 1."
            )
            temperature = 1

        # Get full model name
        model = self._get_full_model_name(model_name)

        # Prepare messages
        messages = await self._aprepare_messages(prompt, system_message, attachments)

        return {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": timeout,
            "user": user,
            "prompt": prompt,
            "structured_output_schema": structured_output_schema,
        }

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
        attachments: Optional[Sequence[Union[Attachment, bytes]]] = None,
        **extra_kwargs,
    ) -> "ModelResponse":
        """
        Async raw query to the LLM - returns the complete response object.

        Args:
            prompt: The text prompt to send to the LLM
            user: User identifier for tracking usage and permissions
            system_message: Optional system message to prepend
            model: Optional model to use (defaults to provider default)
            temperature: Optional temperature setting (0.0-1.0)
            max_tokens: Optional maximum tokens in the response
            timeout: Optional timeout in seconds
            max_retries: Number of retries on failure
            structured_output_schema: Optional Pydantic model for structured output
            attachments: Optional list of attachments to include in the request
            **extra_kwargs: Additional arguments to pass to the LLM provider

        Returns:
            Raw response from the LLM with full metadata and usage stats
        """
        from litellm import acompletion
        from litellm.types.utils import ModelResponse

        # Prepare common parameters
        params = await self._prepare_request(
            prompt=prompt,
            user=user,
            system_message=system_message,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            structured_output_schema=structured_output_schema,
            attachments=attachments,
        )

        # Additional parameters for the API call
        api_params = {
            "temperature": params["temperature"],
            "max_tokens": params["max_tokens"],
            "request_timeout": params["timeout"],
            "num_retries": max_retries,
            **extra_kwargs,
        }

        # Add structured output if needed
        if params["structured_output_schema"]:
            api_params["response_format"] = params["structured_output_schema"]

        logger.debug(f"Async querying LLM with model {params['model']}")

        # Make the actual API call
        response = await acompletion(
            model=params["model"], messages=params["messages"], **api_params
        )

        # Track usage asynchronously (approximate tokens used)
        token_estimate = (len(params["prompt"]) + len(response.choices[0].message.content)) // 4
        await self._track_usage(params["user"], params["model"], token_estimate)

        # Check for the correct response type
        assert isinstance(response, ModelResponse), f"Unknown response type: {type(response)}"

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
        attachments: Optional[Sequence[Union[Attachment, bytes]]] = None,
        **extra_kwargs,
    ) -> str:
        """
        Async query to the LLM returning just the text response.

        Arguments are the same as aquery_llm_raw but returns a string.
        """
        from litellm.types.utils import Choices, ModelResponse

        response = await self.aquery_llm_raw(
            prompt=prompt,
            user=user,
            system_message=system_message,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
            attachments=attachments,
            **extra_kwargs,
        )

        # Extract content with assertions for proper structure
        assert isinstance(response, ModelResponse)

        choice = response.choices[0]
        # Ensure we're dealing with a non-streaming choice that has a message attribute
        assert isinstance(choice, Choices), f"Expected Choices but got {type(choice)}"
        assert choice.message.content is not None, "Message content is None"

        return choice.message.content

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
        attachments: Optional[Sequence[Union[Attachment, bytes]]] = None,
        **extra_kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Async stream text chunks from the LLM.

        Arguments are the same as aquery_llm_raw but returns an async generator of text chunks.
        """
        from litellm import acompletion
        from litellm.litellm_core_utils.streaming_handler import CustomStreamWrapper
        from litellm.types.utils import StreamingChoices

        # Prepare common parameters
        params = await self._prepare_request(
            prompt=prompt,
            user=user,
            system_message=system_message,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            attachments=attachments,
        )

        # Track usage at the start (approximate tokens)
        token_estimate = len(params["prompt"]) // 4 + params["max_tokens"]
        await self._track_usage(params["user"], params["model"], token_estimate)

        # Make the actual API call with streaming
        stream_response = await acompletion(
            model=params["model_name"],
            messages=params["messages"],
            temperature=params["temperature"],
            max_tokens=params["max_tokens"],
            request_timeout=params["timeout"],
            num_retries=max_retries,
            stream=True,
            **extra_kwargs,
        )

        # Ensure we got a streaming response
        assert isinstance(
            stream_response, CustomStreamWrapper
        ), f"Expected streaming response but got: {type(stream_response)}"

        async for chunk in stream_response:
            choice = chunk.choices[0]
            assert isinstance(
                choice, StreamingChoices
            ), f"Expected StreamChoices but got {type(choice)}"
            assert choice.delta.content is not None, "Message content is None"

            yield choice.delta.content

    async def aquery_llm_structured(
        self,
        prompt: str,
        output_schema: Type[T],
        *,
        user: Optional[UserLike] = None,
        system_message: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        max_retries: int = 2,
        attachments: Optional[Sequence[Union[Attachment, bytes]]] = None,
        **kwargs,
    ) -> T:
        """
        Async query LLM with structured output.

        Args:
            output_schema: A Pydantic model class defining the structure
            Other arguments same as aquery_llm_raw

        Returns:
            An instance of the provided Pydantic model
        """
        from litellm.types.utils import Choices

        # Prepare enhanced system message with structured output instructions
        enhanced_system = system_message or ""
        if not enhanced_system.endswith(
            "\nYou MUST respond with a valid JSON object that conforms to the specified schema."
        ):
            enhanced_system += (
                "\nYou MUST respond with a valid JSON object that conforms to the specified schema."
            )

        # Use the raw query with the structured output schema
        response = await self.aquery_llm_raw(
            prompt=prompt,
            user=user,
            system_message=enhanced_system,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
            structured_output_schema=output_schema,
            attachments=attachments,
            **kwargs,
        )

        choice = response.choices[0]
        assert isinstance(choice, Choices), f"Expected Choices but got {type(choice)}"
        assert choice.message.content is not None, "Message content is None"

        # Parse the response into the Pydantic model
        content = choice.message.content
        result_json = json.loads(content)
        return output_schema(**result_json)

    # ---------------------------------------------
    # endregion Asynchronous Query Methods
    # ---------------------------------------------

    @staticmethod
    def _is_o_series_model(model_name: str) -> bool:
        """Check if the model is an O-series model that only supports temperature=1."""
        model_name = model_name.lower()
        return any(
            key in model_name
            for key in [
                "gpt-4o",
                "o1",
                "o3",
                "o4",
                "openai/gpt-4o",
                "openai/o1",
                "openai/o3",
                "openai/o4",
            ]
        )


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

    if settings.drop_unsupported_params:
        import litellm

        litellm.drop_params = True

    # Check if litellm is installed
    try:
        import litellm

        logger.debug("litellm version: %s", litellm.api_version)
    except ImportError:
        logger.error(
            "litellm is not installed. Please install it to use the LLM Provider component."
        )
        raise ImportError(
            "litellm is not installed. Run 'poetry add litellm' or 'pip install litellm'"
        )
    if not settings.skip_import_check:
        to_check = [
            "openai",
            "anthropic",
            "google-generativeai",
            "xai_sdk",
        ]
        ai_libraries = {
            "openai": "openai",  # poetry add openai -> import openai
            "anthropic": "anthropic",  # poetry add anthropic -> import anthropic
            "google-generativeai": "google.generativeai",  # poetry add google-generativeai -> import google.generativeai
            # "xai_sdk": "xai",  # No such library
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
        for lib_name in to_check:
            if lib_name in ai_libraries:
                lib = ai_libraries[lib_name]

                try:
                    __import__(lib)
                    logger.info(f"✅ {lib_name} is available.")
                except ImportError:
                    logger.info(
                        f"❌ {lib_name} is not installed. `poetry add {lib_name}` to install it."
                    )

            env_key = api_keys_env_names[lib_name]
            api_key = os.getenv(env_key)

            if api_key:
                logger.info(f" (✅ {env_key})")
                installed_libraries.append(lib_name)
            else:
                logger.info(f" (❌ No {env_key})")

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


async def aquery_llm_raw(
    prompt: str,
    *,
    user: Optional[Union[int, str]] = None,
    system_message: Optional[str] = None,
    model: Optional[str] = None,
    attachments: Optional[Sequence[Union[Attachment, bytes]]] = None,
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
        attachments: Optional list of attachments to include in the request
        **kwargs: Additional arguments to pass to the LLM provider

    Returns:
        Raw response from the LLM with full metadata and usage stats
    """
    provider = get_llm_provider()
    return await provider.aquery_llm_raw(
        prompt=prompt,
        user=user,
        system_message=system_message,
        model=model,
        attachments=attachments,
        **kwargs,
    )


async def aquery_llm_text(
    prompt: str,
    *,
    user: Optional[Union[int, str]] = None,
    system_message: Optional[str] = None,
    model: Optional[str] = None,
    attachments: Optional[Sequence[Union[Attachment, bytes]]] = None,
    **kwargs,
) -> str:
    """
    Async query the LLM and return the text response.

    This is a convenience function that uses the global LLM provider.
    """
    provider = get_llm_provider()
    return await provider.aquery_llm_text(
        prompt=prompt,
        user=user,
        system_message=system_message,
        model=model,
        attachments=attachments,
        **kwargs,
    )


async def aquery_llm_stream(
    prompt: str,
    *,
    user: Optional[Union[int, str]] = None,
    system_message: Optional[str] = None,
    model: Optional[str] = None,
    attachments: Optional[Sequence[Union[Attachment, bytes]]] = None,
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
        attachments: Optional list of attachments to include in the request
        **kwargs: Additional arguments to pass to the LLM provider

    Returns:
        An async generator that yields text chunks as they become available
    """
    provider = get_llm_provider()
    async for chunk in provider.aquery_llm_stream(
        prompt=prompt,
        user=user,
        system_message=system_message,
        model=model,
        attachments=attachments,
        **kwargs,
    ):
        yield chunk


astream_llm = aquery_llm_stream


async def aquery_llm_structured(
    prompt: str,
    output_schema: Type[T],
    *,
    user: Optional[Union[int, str]] = None,
    system_message: Optional[str] = None,
    model: Optional[str] = None,
    attachments: Optional[Sequence[Union[Attachment, bytes]]] = None,
    **kwargs,
) -> T:
    """
    Async query LLM with structured output.

    This is a convenience function that uses the global LLM provider.
    """
    provider = get_llm_provider()
    return await provider.aquery_llm_structured(
        prompt=prompt,
        output_schema=output_schema,
        user=user,
        system_message=system_message,
        model=model,
        attachments=attachments,
        **kwargs,
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
        from litellm.types.utils import ModelResponse

        prompt = message.text
        assert prompt is not None, "Expected message to have text"
        assert message.from_user is not None, "Expected message to have from_user"
        user_id = message.from_user.id
        provider = get_llm_provider()

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
            prompt="Recommend a sci-fi movie",
            output_schema=MovieRecommendation,
            user=user_id,
        )
        print(f"\n\nMovie: {structured_result.title} ({structured_result.year})")

        # 4. Raw response with full details
        raw_response = await provider.aquery_llm_raw(
            prompt="What's the weather like?", user=user_id
        )
        assert isinstance(raw_response, ModelResponse), "Expected ModelResponse"

        # print(f"\nToken usage: {raw_response.usage}")

    # Run the example with a mock message
    asyncio.run(
        llm_message_handler(
            Message(
                message_id=1,
                date=datetime.now(),
                chat=Chat(id=12345, type="private"),
                text="What is the meaning of life?",
                from_user=User(id=12345, is_bot=False, first_name="Test"),
            )
        )
    )
