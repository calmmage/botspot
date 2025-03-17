"""
Caching utilities for Botspot.
"""

import time
from collections import OrderedDict
from typing import Any, Callable, Dict, TypeVar, cast

T = TypeVar("T")


class AsyncLRUCache:
    """
    LRU cache for async functions.

    This cache is designed to work with async functions where standard functools.lru_cache
    would fail with "cannot reuse already awaited coroutine" errors.

    Features:
    - LRU (Least Recently Used) eviction policy
    - Optional TTL (Time To Live) for cached entries
    - Thread-safe for async usage

    Example usage:
    ```python
    # Create a cache instance
    _my_cache = AsyncLRUCache(maxsize=100, ttl=300)  # 5-minute TTL

    async def get_cached_data(key):
        # Define a factory function that returns a fresh coroutine
        async def _get_fresh_data():
            # Your expensive async operation here
            return await fetch_data_from_db(key)

        # Use the cache
        return await _my_cache.get_or_set(key, _get_fresh_data)
    ```
    """

    def __init__(self, maxsize: int = 128, ttl: float = None):
        """
        Initialize the async LRU cache.

        Args:
            maxsize: Maximum number of entries to keep in the cache
            ttl: Time-to-live in seconds (None means no expiration)
        """
        self.maxsize = maxsize
        self.ttl = ttl  # Time-to-live in seconds
        self.cache: OrderedDict[Any, Dict[str, Any]] = OrderedDict()

    async def get_or_set(self, key: Any, coroutine_factory: Callable[[], T]) -> T:
        """
        Get a value from cache or set it using the coroutine factory.

        Args:
            key: Cache key
            coroutine_factory: Function that returns a fresh coroutine to get the value
                               Important: this must return a NEW coroutine each time

        Returns:
            The cached or newly fetched value
        """
        now = time.time()

        # If key in cache and not expired, return it
        if key in self.cache:
            value, timestamp = self.cache[key]
            # Move to end (most recently used)
            self.cache.move_to_end(key)

            # Check if expired
            if self.ttl is None or now - timestamp < self.ttl:
                return cast(T, value)

            # If expired, remove it
            del self.cache[key]

        # Cache miss or expired, create a new coroutine and execute it
        coro = coroutine_factory()
        result = await coro

        # Add to cache
        self.cache[key] = (result, now)

        # Enforce size limit
        if len(self.cache) > self.maxsize:
            self.cache.popitem(last=False)

        return result
