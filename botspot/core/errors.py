from typing import Optional


class BotspotError(Exception):
    def __init__(
        self,
        message: str,
        report_to_dev: bool = True,
        include_traceback: bool = True,
        user_message: Optional[str] = None,
        easter_eggs: bool = True,
        *args: object,
    ) -> None:
        self.message = message
        self.report_to_dev = report_to_dev
        self.include_traceback = include_traceback
        self.user_message = user_message
        self.easter_eggs = easter_eggs
        super().__init__(*args)


# Core errors
class ConfigurationError(BotspotError):
    """Raised when there is an issue with the bot configuration."""

    pass


class DependencyError(BotspotError):
    """Raised when there is an issue with component dependencies."""

    pass


# Data component errors
class DatabaseError(BotspotError):
    """Raised when there is a database-related issue."""

    pass


class UserDataError(BotspotError):
    """Raised when there is an issue with user data management."""

    pass


class ContactDataError(BotspotError):
    """Raised when there is an issue with contact data management."""

    pass


# New component errors
class ChatBinderError(BotspotError):
    """Raised when there is an issue with chat binding functionality."""

    pass


class ChatBindingExistsError(ChatBinderError):
    """Raised when attempting to bind a chat that is already bound."""

    pass


class ChatBindingNotFoundError(ChatBinderError):
    """Raised when attempting to access a chat binding that doesn't exist."""

    pass


class ChatAccessError(ChatBinderError):
    """Raised when the bot lacks necessary permissions in a chat."""

    pass


class LLMProviderError(BotspotError):
    """Raised when there is an issue with the LLM provider."""

    pass


class LLMAuthenticationError(LLMProviderError):
    """Raised when there is an issue with LLM API authentication."""

    pass


class LLMRateLimitError(LLMProviderError):
    """Raised when API rate limits are exceeded."""

    pass


class LLMPermissionError(LLMProviderError):
    """Raised when a user lacks permission to use LLM features."""

    pass


class LLMResponseError(LLMProviderError):
    """Raised when there is an issue with an LLM response."""

    pass


class LLMStructuredOutputError(LLMResponseError):
    """Raised when there is an issue parsing structured output from an LLM."""

    pass


class QueueManagerError(BotspotError):
    """Raised when there is an issue with the queue manager."""

    pass


class QueueNotFoundError(QueueManagerError):
    """Raised when attempting to access a queue that doesn't exist."""

    pass


class QueueItemValidationError(QueueManagerError):
    """Raised when a queue item fails validation."""

    pass


class QueuePermissionError(QueueManagerError):
    """Raised when a user lacks permission to interact with a queue."""

    pass


class ChatFetcherError(BotspotError):
    """Raised when there is an issue with chat fetching functionality."""

    pass


class ChatFetchAccessError(ChatFetcherError):
    """Raised when the bot lacks access to fetch messages from a chat."""

    pass


class MessageRetrievalError(ChatFetcherError):
    """Raised when messages cannot be retrieved from Telegram."""

    pass


class RateLimitError(ChatFetcherError):
    """Raised when Telegram API rate limits are exceeded."""

    pass


class ContextBuilderError(BotspotError):
    """Raised when there is an issue with context building functionality."""

    pass


class ContextLimitExceededError(ContextBuilderError):
    """Raised when the context size exceeds token limits."""

    pass


class ContextMissingError(ContextBuilderError):
    """Raised when required context information is missing."""

    pass


class AutoArchiveError(BotspotError):
    """Raised when there is an issue with auto-archiving functionality."""

    pass


class ArchiveOperationError(AutoArchiveError):
    """Raised when an archive operation fails."""

    pass


class ArchivePermissionError(AutoArchiveError):
    """Raised when there are permission issues for archive operations."""

    pass


class ArchiveStorageError(AutoArchiveError):
    """Raised when archive storage limits are exceeded."""

    pass


# Feature component errors
class TelethonManagerError(BotspotError):
    """Raised when there is an issue with Telethon manager functionality."""

    pass


class TelethonSessionError(TelethonManagerError):
    """Raised when there is an issue with Telethon session."""

    pass


class TelethonConnectionError(TelethonManagerError):
    """Raised when there is a connection issue with Telegram API."""

    pass


class TelethonClientNotConnectedError(TelethonConnectionError):
    """Raised when trying to use Telethon client before it's properly connected.

    This error indicates that the user needs to run the /setup_telethon command
    to complete the authentication and connection process.
    """

    def __init__(
        self,
        message: str = "Telethon client is not connected. Please run the /setup_telethon command to authenticate.",
        report_to_dev: bool = True,
        include_traceback: bool = True,
        user_message: Optional[
            str
        ] = "Telethon client is not connected. Please run the /setup_telethon command to authenticate.",
        easter_eggs: bool = False,
        *args: object,
    ) -> None:
        super().__init__(
            message=message,
            report_to_dev=report_to_dev,
            include_traceback=include_traceback,
            user_message=user_message,
            easter_eggs=easter_eggs,
            *args,
        )


class TelethonAuthError(TelethonManagerError):
    """Raised when there is an authentication issue with Telegram API."""

    pass


class SubscriptionManagerError(BotspotError):
    """Raised when there is an issue with subscription management."""

    pass


class SubscriptionPaymentError(SubscriptionManagerError):
    """Raised when there is an issue processing subscription payments."""

    pass


class SubscriptionValidationError(SubscriptionManagerError):
    """Raised when there is an issue validating a subscription."""

    pass


class SubscriptionQuotaError(SubscriptionManagerError):
    """Raised when a user exceeds their subscription quota."""

    pass


class EventSchedulerError(BotspotError):
    """Raised when there is an issue with event scheduling."""

    pass


class ScheduleConflictError(EventSchedulerError):
    """Raised when there is a scheduling conflict."""

    pass


class ScheduleMissedError(EventSchedulerError):
    """Raised when a scheduled event is missed."""

    pass


class ScheduleTimeFormatError(EventSchedulerError):
    """Raised when there is an issue with time format for scheduling."""

    pass
