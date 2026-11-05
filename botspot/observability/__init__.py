"""Product metrics for botspot bots; standalone writers live in ``.client``."""

from .client import ObservabilityClient, log_sink, record_event


async def record_usage(kind: str, **fields):
    """Record a product event using the bot's configured observability component."""
    from botspot.utils.deps_getters import get_observability

    component = get_observability()
    if component is not None:
        await component.client.record_usage(kind, **fields)


__all__ = ["ObservabilityClient", "log_sink", "record_event", "record_usage"]
