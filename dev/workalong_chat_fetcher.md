# Chat Fetcher Component Integration

## Task

Integrate telegram-downloader as a dependency into the chat_fetcher component, similar
to how calmlib is integrated.

## Current Implementation Status

1. Added telegram-downloader as a dependency in pyproject.toml:

```
telegram-downloader = { git = "https://github.com/calmmage/telegram-downloader.git", branch = "main" }
```

2. Enhanced ChatFetcherSettings with telegram-downloader specific configuration:

- Added separate collections for messages and chats
- Added configuration for storage mode
- Added parameters for download limits (backdays, message limits, etc.)

3. Created a wrapper around telegram-downloader in the ChatFetcher class:

- Created conversion methods between ChatData and ChatModel
- Added methods to initialize and use TelegramDownloader
- Implemented fallback mechanisms for reliability
- Added separate messages and chats collections

## Current Limitations

Currently, the integration has a major limitation: telegram-downloader doesn't support:

- Accepting a custom MongoDB connection
- Using an external Telethon client

Instead, it creates its own connections internally, which creates inefficiency and
potential conflicts.

## Required Changes to telegram-downloader

To properly integrate telegram-downloader with botspot, we need to modify the
telegram-downloader package:

1. In `TelegramDownloader.__init__()`:
    - Add parameters for external Telethon client:
      `external_client: Optional[TelegramClient] = None`
    - Add parameters for external MongoDB database:
      `external_db: Optional[Database] = None`

2. In `get_telethon_client()` method:
    - Check if an external client was provided and use it if available
    - Fall back to creating a new client only if needed

3. In database-related methods:
    - Use the external database connection if provided
    - Only create a new connection if not provided

4. Update the `TelethonClientManager` class:
    - Add support for using an existing client
    - Add method to register an external client

## Implementation Plan

1. Create a fork of telegram-downloader
2. Make the necessary modifications:
    - Update TelegramDownloader class
    - Update TelethonClientManager
    - Add tests for external client/DB support
3. Submit a pull request to the original repository
4. Update the botspot chat_fetcher component to use these new features

## Example Code Changes (Draft)

```python
# In telegram_downloader.py
def __init__(self, config_path: Path | str = Path("config.yaml"),
             external_client: Optional[TelegramClient] = None,
             external_db: Optional[Database] = None,
             **kwargs):
    self.env = TelegramDownloaderEnvSettings(**kwargs)

    config_path = Path(config_path)
    self.config = TelegramDownloaderConfig.from_yaml(config_path, **kwargs)

    self._external_client = external_client
    self._external_db = external_db
    self._db = None
    self._telethon_client = None
    self.reset_properties()


async def get_telethon_client(self) -> TelegramClient:
    if self._telethon_client is not None:
        return self._telethon_client

    if self._external_client is not None:
        self._telethon_client = self._external_client
        return self._telethon_client

    # Original code for creating a client...
```

## Next Steps

1. Discuss this approach - confirm if this matches the intended integration
2. Determine whether to:
    - Fork telegram-downloader and implement these changes
    - Create a pull request to upstream repository
    - Or use a simpler approach like copying select code
3. Test the implementation with a real bot
4. Document the API and provide usage examples