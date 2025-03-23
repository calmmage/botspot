"""
Context Builder Component

Collects messages forwarded together and bundles them as a single context object.
"""
from typing import Any, Awaitable, Callable, Dict, List, Optional
from datetime import datetime, timedelta

from aiogram import Dispatcher
from aiogram.types import Message, TelegramObject, Update
from pydantic import Field
from pydantic_settings import BaseSettings

from botspot.utils.internal import get_logger

logger = get_logger()


class ContextBuilderSettings(BaseSettings):
    enabled: bool = False
    bundle_timeout: float = 0.5  # Time window in seconds to bundle messages
    include_replies: bool = True
    include_forwards: bool = True
    include_media: bool = True
    include_text: bool = True

    class Config:
        env_prefix = "BOTSPOT_CONTEXT_BUILDER_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class MessageContext:
    """Represents a bundle of messages that form a context."""
    
    def __init__(self):
        self.messages: List[Message] = []
        self.last_update_time: datetime = datetime.now()
        self.text_content: str = ""
        self.media_descriptions: List[str] = []
        
    def add_message(self, message: Message) -> None:
        """Add a message to the context bundle."""
        self.messages.append(message)
        self.last_update_time = datetime.now()
        
        # Extract text content
        if message.text:
            if self.text_content:
                self.text_content += f"\n\n{message.text}"
            else:
                self.text_content = message.text
        
        # Extract media descriptions
        if message.photo:
            self.media_descriptions.append("[Image]")
        elif message.video:
            self.media_descriptions.append("[Video]")
        elif message.voice:
            self.media_descriptions.append("[Voice Message]")
        elif message.audio:
            self.media_descriptions.append("[Audio]")
        elif message.document:
            self.media_descriptions.append(f"[Document: {message.document.file_name}]")
    
    def is_expired(self, timeout_seconds: float) -> bool:
        """Check if the context has expired based on timeout."""
        return (datetime.now() - self.last_update_time) > timedelta(seconds=timeout_seconds)
    
    def get_combined_text(self) -> str:
        """Get the combined text from all messages in the context."""
        return self.text_content
    
    def get_full_context(self) -> str:
        """Get the full context including text and media descriptions."""
        result = self.text_content
        if self.media_descriptions:
            media_text = "\n".join(self.media_descriptions)
            if result:
                result += f"\n\n{media_text}"
            else:
                result = media_text
        return result


class ContextBuilder:
    """Component that builds context from multiple messages."""
    
    def __init__(self, settings: ContextBuilderSettings):
        self.settings = settings
        self.message_contexts: Dict[int, MessageContext] = {}  # chat_id -> MessageContext
        
    async def build_context(self, message: Message) -> Optional[str]:
        """
        Build context from a message and its related messages.
        Returns the current context text if available.
        """
        chat_id = message.chat.id
        
        # Process message based on settings
        context_text = None
        
        # Get or create message context for this chat
        if chat_id not in self.message_contexts:
            self.message_contexts[chat_id] = MessageContext()
        
        context = self.message_contexts[chat_id]
        
        # If context has expired, create a new one
        if context.is_expired(self.settings.bundle_timeout):
            # If there were messages in the previous context, we consider it complete
            if context.messages:
                context_text = context.get_full_context()
            # Start a new context
            self.message_contexts[chat_id] = MessageContext()
            context = self.message_contexts[chat_id]
        
        # Add the current message to the context
        context.add_message(message)
        
        return context_text


async def context_builder_middleware(
    handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
    event: Update,
    data: Dict[str, Any],
) -> Any:
    """
    Middleware that builds context from messages and adds it to the message metadata.
    """
    # Only process message events
    if not hasattr(event, "message") or event.message is None or not isinstance(event.message, Message):
        return await handler(event, data)
    
    message = event.message
    
    from botspot.core.dependency_manager import get_dependency_manager
    deps = get_dependency_manager()
    
    if not hasattr(deps, "context_builder"):
        return await handler(event, data)
    
    context_builder = deps.context_builder
    
    # Build context from the message
    context_text = await context_builder.build_context(message)
    
    # Add context to message data
    if context_text:
        logger.debug(f"Adding context to message data: {context_text[:100]}...")
        data["context_text"] = context_text
    
    # Set metadata flag to indicate that this message is part of a context bundle
    data["is_in_context_bundle"] = True
    
    return await handler(event, data)


def setup_dispatcher(dp: Dispatcher):
    """Set up the context builder middleware."""
    logger.debug("Adding context builder middleware")
    dp.update.middleware(context_builder_middleware)
    return dp


def initialize(settings: ContextBuilderSettings) -> ContextBuilder:
    """Initialize the context builder component."""
    logger.info("Initializing context builder component")
    return ContextBuilder(settings)


def get_context_builder() -> ContextBuilder:
    """Get the context builder from the dependency manager."""
    from botspot.core.dependency_manager import get_dependency_manager
    deps = get_dependency_manager()
    return deps.context_builder