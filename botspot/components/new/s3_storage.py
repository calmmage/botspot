from typing import Optional, AsyncGenerator, BinaryIO
from pydantic_settings import BaseSettings
from loguru import logger


class S3StorageSettings(BaseSettings):
    """Settings for the S3 Storage component."""

    enabled: bool = False
    bucket_name: str = ""
    region: str = ""
    access_key_id: str = ""
    secret_access_key: str = ""
    skip_import_check: bool = False

    class Config:
        env_prefix = "BOTSPOT_S3_STORAGE_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class S3StorageProvider:
    """Main S3 Storage provider class for Botspot"""

    def __init__(self, settings: S3StorageSettings):
        """Initialize the S3 Storage Provider with the given settings."""
        self.settings = settings
        self._client = None

    async def _get_client(self):
        """Get or create the S3 client with lazy loading."""
        if self._client is None:
            try:
                import aioboto3

                session = aioboto3.Session()
                self._client = await session.client(
                    "s3",
                    region_name=self.settings.region,
                    aws_access_key_id=self.settings.access_key_id,
                    aws_secret_access_key=self.settings.secret_access_key,
                ).__aenter__()
            except ImportError as e:
                if not self.settings.skip_import_check:
                    logger.error(
                        "aioboto3 is not installed. Please install it to use the S3 Storage component."
                    )
                    raise ImportError(
                        "aioboto3 is not installed. Run 'poetry add aioboto3' or 'pip install aioboto3'"
                    )
                raise e
        return self._client

    async def upload_file(self, key: str, content: bytes) -> None:
        """Upload a file to S3."""
        client = await self._get_client()
        await client.put_object(Bucket=self.settings.bucket_name, Key=key, Body=content)

    async def download_file(self, key: str) -> bytes:
        """Download a file from S3."""
        client = await self._get_client()
        response = await client.get_object(Bucket=self.settings.bucket_name, Key=key)
        return await response["Body"].read()

    async def delete_file(self, key: str) -> None:
        """Delete a file from S3."""
        client = await self._get_client()
        await client.delete_object(Bucket=self.settings.bucket_name, Key=key)

    async def list_files(self, prefix: str = "") -> AsyncGenerator[str, None]:
        """List files in S3 with optional prefix."""
        client = await self._get_client()
        paginator = client.get_paginator("list_objects_v2")
        async for page in paginator.paginate(
            Bucket=self.settings.bucket_name, Prefix=prefix
        ):
            for obj in page.get("Contents", []):
                yield obj["Key"]

    async def upload_file_stream(self, key: str, stream: BinaryIO) -> None:
        """Upload a file from a stream to S3."""
        client = await self._get_client()
        await client.upload_fileobj(stream, self.settings.bucket_name, key)

    async def download_file_stream(self, key: str) -> AsyncGenerator[bytes, None]:
        """Download a file from S3 as a stream."""
        client = await self._get_client()
        response = await client.get_object(Bucket=self.settings.bucket_name, Key=key)
        async for chunk in response["Body"].iter_chunks():
            yield chunk


def initialize(settings: S3StorageSettings) -> Optional[S3StorageProvider]:
    """Initialize the S3 Storage component."""
    if not settings.enabled:
        logger.info("S3 Storage component is disabled")
        return None

    # Check if aioboto3 is installed
    try:
        import aioboto3

        logger.debug("aioboto3 version: %s", aioboto3.__version__)
    except ImportError:
        if not settings.skip_import_check:
            logger.error(
                "aioboto3 is not installed. Please install it to use the S3 Storage component."
            )
            raise ImportError(
                "aioboto3 is not installed. Run 'poetry add aioboto3' or 'pip install aioboto3'"
            )

    logger.info("Initializing S3 Storage component")
    provider = S3StorageProvider(settings)
    return provider
